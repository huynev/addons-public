/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AttendanceDashboard extends Component {
    static template = "AttendanceDashboardTemplate";

    setup() {
        this.rpc = useService("rpc");
        this.containerRef = useRef("container");
        this.state = useState({
            data: {
                checked_in: [],
                not_checked_in: [],
                checked_out: [],
                total_employees: 0,
                last_update: '--:--:--'
            },
            loading: false
        });

        onMounted(() => {
            this.loadData();
            this.startAutoRefresh();
        });

        onWillUnmount(() => {
            this.stopAutoRefresh();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.rpc('/attendance/dashboard/data', {});
            this.state.data = data;
            this.updateUI();
        } catch (error) {
            console.error('Error loading attendance data:', error);
        } finally {
            this.state.loading = false;
        }
    }

    updateUI() {
        const data = this.state.data;
        const container = this.containerRef.el;
        if (!container) return;

        // Update counters
        const checkedInCount = container.querySelector('#checked_in_count');
        const notCheckedInCount = container.querySelector('#not_checked_in_count');
        const checkedOutCount = container.querySelector('#checked_out_count');
        const totalCount = container.querySelector('#total_count');
        const lastUpdate = container.querySelector('#last_update');

        if (checkedInCount) checkedInCount.textContent = data.checked_in.length;
        if (notCheckedInCount) notCheckedInCount.textContent = data.not_checked_in.length;
        if (checkedOutCount) checkedOutCount.textContent = data.checked_out.length;
        if (totalCount) totalCount.textContent = data.total_employees;
        if (lastUpdate) lastUpdate.textContent = `Last updated: ${data.last_update}`;

        // Update title counters
        const checkedInTitleCount = container.querySelector('#checked_in_title_count');
        const notCheckedInTitleCount = container.querySelector('#not_checked_in_title_count');
        const checkedOutTitleCount = container.querySelector('#checked_out_title_count');

        if (checkedInTitleCount) checkedInTitleCount.textContent = data.checked_in.length;
        if (notCheckedInTitleCount) notCheckedInTitleCount.textContent = data.not_checked_in.length;
        if (checkedOutTitleCount) checkedOutTitleCount.textContent = data.checked_out.length;

        // Update employee grids
        this.updateEmployeeGrid(container, 'checked_in_grid', data.checked_in, 'checked_in');
        this.updateEmployeeGrid(container, 'not_checked_in_grid', data.not_checked_in, 'not_checked_in');
        this.updateEmployeeGrid(container, 'checked_out_grid', data.checked_out, 'checked_out');
    }

    updateEmployeeGrid(container, gridId, employees, type) {
        const grid = container.querySelector(`#${gridId}`);
        if (!grid) return;

        grid.innerHTML = '';

        employees.forEach(employee => {
            const card = document.createElement('div');
            card.className = `employee_card ${type}_employee`;

            let timeInfo = '';
            if (type === 'checked_in') {
                timeInfo = `
                    <div class="time_info">
                        <span class="check_in_time">In: ${employee.check_in_time}</span>
                        <span class="working_hours">${employee.working_hours}</span>
                    </div>
                `;
            } else if (type === 'checked_out') {
                timeInfo = `
                    <div class="time_info">
                        <span class="check_times">
                            In: ${employee.check_in_time} | Out: ${employee.check_out_time}
                        </span>
                        <span class="worked_hours">${employee.worked_hours}</span>
                    </div>
                `;
            }

            card.innerHTML = `
                <div class="employee_avatar">
                    <img src="${employee.image_url}" alt="${employee.name}" onerror="this.src='/hr/static/src/img/default_image.png'">
                </div>
                <div class="employee_info">
                    <h4 class="employee_name">${employee.name}</h4>
                    <p class="employee_department">${employee.department}</p>
                    <p class="employee_job">${employee.job_title}</p>
                    ${timeInfo}
                </div>
            `;

            grid.appendChild(card);
        });

        if (employees.length === 0) {
            grid.innerHTML = '<div class="no_employees">No employees in this category</div>';
        }
    }

    onRefreshClick() {
        this.loadData();
    }

    startAutoRefresh() {
        // Refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.loadData();
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

registry.category("actions").add("attendance_dashboard", AttendanceDashboard);