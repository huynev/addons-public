/** @odoo-module **/

import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { getReportUrl } from "@web/webclient/actions/reports/utils";

registry
    .category("ir.actions.report handlers")
    .add("action_custom", async function (action, options, env) {
        const type = action.report_type.slice(5);
        const url = getReportUrl(action, type);
        if (action.report_type !== "qweb-html" && action.report_type !== "xlsx") {
            env.services.ui.block();
            $('#frame-pdf').remove();
            $('<iframe style="display: none;">')
                .attr({ id: 'frame-pdf', src: url, name: 'frame-pdf' })
                .appendTo(document.body)
                .on( "load", function (responseText, textStatus, jqXHR) {
                    window.frames['frame-pdf'].focus();
                    window.frames['frame-pdf'].print();
                    if (options.complete) {
                        options.complete();
                    }
                    env.services.ui.unblock();
                });
            return Promise.resolve(true);
        }
        return Promise.resolve(false);
    });
