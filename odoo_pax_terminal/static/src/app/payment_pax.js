/*
    Copyright 2024 Your Company
    License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
*/
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

export class PaymentPax extends PaymentInterface {
    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    setup() {
        super.setup(...arguments);
        this.enable_reversals();

        // Get terminal IP from payment method
        var terminal_ip = this.payment_method_id.pax_terminal_ip;

        // Check if there's already an instanced payment method with the same terminal
        var instanced_payment_method = this.pos.models["pos.payment.method"].find(function (
            payment_method
        ) {
            return (
                payment_method.use_payment_terminal === "pax" &&
                payment_method.pax_terminal_ip === terminal_ip &&
                payment_method.payment_terminal
            );
        });

        if (instanced_payment_method !== undefined) {
            var payment_terminal = instanced_payment_method.payment_terminal;
            this.terminal = payment_terminal.terminal;
            this.paxConnection = payment_terminal.paxConnection;
            return;
        }

        // Initialize PAX terminal connection
        this._initPaxTerminal();
    }

    /**
     * @override
     */
    send_payment_cancel() {
        super.send_payment_cancel(...arguments);
        if (this.paxConnection && this.paxConnection.cancel) {
            this.paxConnection.cancel();
        }
        this._show_error(_t("Payment cancelled. Please check the terminal."));
        return Promise.resolve(true);
    }

    /**
     * @override
     */
    send_payment_request() {
        super.send_payment_request(...arguments);
        this.pos.get_order().get_selected_paymentline().set_payment_status("waitingCard");
        return this._sendPaxTransaction('purchase');
    }

    /**
     * @override
     */
    send_payment_reversal() {
        super.send_payment_reversal(...arguments);
        this.pos.get_order().get_selected_paymentline().set_payment_status("reversing");
        return this._sendPaxTransaction('reversal');
    }

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _initPaxTerminal() {
        try {
            // Get PAX terminal configuration
            const terminal_config = this._getPaxTerminalConfig();

            if (!terminal_config) {
                console.error('PAX terminal not configured properly');
                return;
            }

            // Store terminal configuration
            this.terminal = {
                ip: terminal_config.ip_address,
                port: terminal_config.port || 80,
                timeout: terminal_config.timeout || 120,
                demo_mode: terminal_config.demo_mode || false,
                default_clerk_id: terminal_config.default_clerk_id || ''
            };

            // Initialize PAX connection object
            this.paxConnection = {
                isConnected: false,
                cancel: this._cancelPaxTransaction.bind(this)
            };

            console.log('PAX terminal initialized:', this.terminal);
        } catch (error) {
            console.error('Error initializing PAX terminal:', error);
        }
    }

    _getPaxTerminalConfig() {
        // Method 1: Try to get terminal ID from payment method
        let terminalId = null;
        let terminal = null;

        // Check if PAX terminal is configured in payment method
        if (this.payment_method_id.pax_terminal_id) {
            // Get terminal ID - handle both array and single value
            terminalId = Array.isArray(this.payment_method_id.pax_terminal_id)
                ? this.payment_method_id.pax_terminal_id[0]
                : this.payment_method_id.pax_terminal_id;

            // Find the terminal in loaded data
            terminal = this.pos.models['pax.terminal']?.get(terminalId);

            if (terminal) {
                console.log('PAX terminal found by payment method ID:', terminalId);
                return terminal;
            }
        }

        // Method 2: Try to get first available terminal (fallback)
        terminal = this.pos.getFirstAvailablePaxTerminal?.();
        if (terminal) {
            console.log('Using first available PAX terminal:', terminal.id);
            return terminal;
        }

        // Method 3: Try hardcoded terminal ID (for testing)
        terminal = this.pos.models['pax.terminal']?.get(1);
        if (terminal) {
            console.log('Using hardcoded PAX terminal ID: 1');
            return terminal;
        }

        // No terminal found
        console.error('PAX terminal not found. Checked terminal ID:', terminalId);
        console.error('Available terminals:', Array.from(this.pos.models['pax.terminal']?.keys() || []));
        return null;
    }

    _sendPaxTransaction(transactionType) {
        const order = this.pos.get_order();
        const pay_line = order.get_selected_paymentline();

        // Validate terminal configuration
        if (!this.terminal) {
            const error_msg = _t('PAX terminal not initialized');
            return Promise.resolve(this._handle_error(error_msg));
        }

        // Prepare transaction data
        const data = {
            amount: pay_line.amount,
            currency_id: this.pos.currency.id,
            payment_method_id: this.payment_method_id.id,
            payment_id: this._generatePaymentId(),
            timeout: this.terminal.timeout * 1000,
            transaction_type: this.payment_method_id.pax_transaction_type || '01',
            reference: order.name || 'POS-' + Date.now(),
            capture_signature: this.payment_method_id.pax_capture_signature || false,
            clerk_id: this.payment_method_id.pax_clerk_id || this.terminal.default_clerk_id || '',
            terminal_ip: this.terminal.ip,
            terminal_port: this.terminal.port,
            type: transactionType
        };

        // Show appropriate message based on mode and transaction type
        this._showTransactionMessage(transactionType);

        return new Promise((resolve) => {
            this.transactionResolve = resolve;
            this._processPaxPayment(data);
        });
    }

    _processPaxPayment(data) {
        this.pos.data
            .silentCall("pos.payment.method", "pax_send_payment", [data])
            .then((response) => {
                this._onPaxTransactionComplete(response);
            })
            .catch((error) => {
                console.error('PAX payment error:', error);
                this._onPaxTransactionError(error);
            });
    }

    _onPaxTransactionComplete(response) {
        const pay_line = this.pos.get_order().get_selected_paymentline();

        if (response instanceof Object && "payment_status" in response) {
            const success = this._handle_pax_response(pay_line, response);

            // Handle receipt printing if available
            if (response.receipt_data) {
                this._handlePaxReceipts(response.receipt_data, pay_line);
            }

            this.transactionResolve(success);
        } else {
            // Unexpected response
            this._handle_pax_unexpected_response(pay_line);
            this.transactionResolve(false);
        }
    }

    _onPaxTransactionError(error) {
        const error_msg = _t("No answer from the payment terminal in the given time.");
        this._handle_error(error_msg);
        this.transactionResolve(false);
    }

    _handle_pax_response(pay_line, response) {
        if (response.payment_status === "success") {
            // Store transaction data
            pay_line.card_type = response.card_type;
            pay_line.transaction_id = response.transaction_id;
            pay_line.pax_transaction_log_id = response.pax_transaction_log_id;

            // Set receipt info
            let receiptInfo = `Card: ${response.card_type}`;
            if (response.demo_mode || this.terminal.demo_mode) {
                receiptInfo += ' (DEMO)';
            }

            if (response.ticket) {
                pay_line.set_receipt_info(response.ticket);
            } else {
                pay_line.set_receipt_info(receiptInfo);
            }

            // Show success notification
            const message = (response.demo_mode || this.terminal.demo_mode)
                ? _t('Demo payment approved successfully')
                : _t('Payment approved successfully');

            this.env.services.notification.add(message, {
                type: 'success',
                sticky: false,
            });

            return true;
        } else {
            const errorMsg = response.error_message || _t('Payment failed');
            return this._handle_error(errorMsg);
        }
    }

    _handle_pax_unexpected_response(pay_line) {
        // The response cannot be understood
        // We let the cashier handle it manually (force or cancel)
        pay_line.set_payment_status("force_done");
        return Promise.reject();
    }

    _handlePaxReceipts(receiptData, pay_line) {
        if (receiptData.merchant_receipt && this.pos.hardwareProxy.printer) {
            // Print merchant receipt
            this.pos.hardwareProxy.printer.printReceipt(
                "<div class='pos-receipt'><div class='pos-payment-terminal-receipt'>" +
                    receiptData.merchant_receipt.replace(/\n/g, "<br />") +
                "</div></div>"
            );
        }

        if (receiptData.customer_receipt) {
            // Set customer receipt info
            pay_line.set_receipt_info(receiptData.customer_receipt);
        }
    }

    _showTransactionMessage(transactionType) {
        let message;

        console.log("this.terminal.demo_mode");
        console.log(this.terminal.demo_mode);
        if (this.terminal.demo_mode) {
            if (transactionType === 'reversal') {
                message = _t('Demo Mode: Simulating PAX reversal...');
            } else {
                message = _t('Demo Mode: Simulating PAX payment...');
            }
        } else {
            if (transactionType === 'reversal') {
                message = _t('Processing reversal on PAX terminal');
            } else {
                message = _t('Please follow instructions on PAX terminal');
            }
        }

        this.env.services.notification.add(message, {
            type: 'info',
            sticky: false,
        });
    }

    _cancelPaxTransaction() {
        // Cancel the current PAX transaction
        console.log('Cancelling PAX transaction');

        // You would implement the actual cancellation logic here
        // This might involve sending a cancellation command to the terminal
    }

    _generatePaymentId() {
        return 'PAX-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    }

    _handle_error(msg) {
        this._show_error(msg);
        return false;
    }

    _show_error(msg, title) {
        this.env.services.dialog.add(AlertDialog, {
            title: title || _t("PAX Payment Terminal Error"),
            body: msg,
        });
    }
}