from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import base64
import io
import pandas as pd
from datetime import datetime


class EmployeeImportWizard(models.TransientModel):
    _name = 'employee.import.wizard'
    _description = 'Employee Import Wizard'

    file_data = fields.Binary('Excel File', required=True)
    file_name = fields.Char('File Name')
    sheet_name = fields.Char('Sheet Name', default='Sheet1')
    employee_code_column = fields.Char('Employee Code Column', default='Mã NV', required=True)
    update_existing = fields.Boolean('Update Existing Employees', default=True)
    create_new = fields.Boolean('Create New Employees', default=False)

    # Column mapping fields
    name_column = fields.Char('Name Column', default='Họ & tên')
    email_column = fields.Char('Email Column', default='Email')
    phone_column = fields.Char('Phone Column', default='Dien Thoai')
    department_column = fields.Char('Department Column', default='Phong Ban')
    job_title_column = fields.Char('Job Title Column', default='Chuc Vu')
    work_location_column = fields.Char('Work Location Column', default='Noi Lam Viec')
    birthday_column = fields.Char('Birthday Column', default='Ngày sinh')
    gender_column = fields.Char('Gender Column', default='Giới tính')
    marital_column = fields.Char('Marital Status Column', default='TT.Hôn Nhân')
    identification_column = fields.Char('Identification No Column', default='Số CMT')
    address_column = fields.Char('Address Column', default='Địa chỉ thường trú')
    hire_date_column = fields.Char('Hire Date Column', default='Ngày vào làm')

    # Results
    import_results = fields.Html('Import Results', readonly=True)

    def _read_excel_file(self):
        """Read Excel file and return DataFrame"""
        try:
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content), sheet_name=self.sheet_name)
            return df
        except Exception as e:
            raise UserError(_('Error reading Excel file: %s') % str(e))

    def _get_or_create_department(self, dept_name):
        """Get or create department"""
        if not dept_name:
            return False

        department = self.env['hr.department'].search([('name', '=', dept_name)], limit=1)
        if not department:
            department = self.env['hr.department'].create({'name': dept_name})
        return department.id

    def _get_or_create_job(self, job_title):
        """Get or create job position"""
        if not job_title:
            return False

        job = self.env['hr.job'].search([('name', '=', job_title)], limit=1)
        if not job:
            job = self.env['hr.job'].create({'name': job_title})
        return job.id

    def _parse_date(self, date_value):
        """Parse date from various formats"""
        if pd.isna(date_value):
            return False

        if isinstance(date_value, datetime):
            return date_value.date()

        if isinstance(date_value, str):
            try:
                # Try different date formats
                for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                    try:
                        return datetime.strptime(date_value, fmt).date()
                    except ValueError:
                        continue
            except:
                pass
        return False

    def _parse_gender(self, gender_value):
        """Parse gender value"""
        if pd.isna(gender_value):
            return 'other'

        gender_str = str(gender_value).lower().strip()
        if gender_str in ['nam', 'male', 'm']:
            return 'male'
        elif gender_str in ['nu', 'nữ', 'female', 'f']:
            return 'female'
        else:
            return 'other'

    def _parse_marital(self, marital_value):
        """Parse marital status"""
        if pd.isna(marital_value):
            return 'single'

        marital_str = str(marital_value).lower().strip()
        if marital_str in ['married', 'da ket hon', 'đã kết hôn', 'co gia dinh']:
            return 'married'
        elif marital_str in ['single', 'doc than', 'độc thân', 'chua ket hon']:
            return 'single'
        elif marital_str in ['widower', 'goa', 'góa']:
            return 'widower'
        elif marital_str in ['divorced', 'ly hon', 'ly dị']:
            return 'divorced'
        else:
            return 'single'

    def action_import_employees(self):
        """Main import action"""
        if not self.file_data:
            raise UserError(_('Please select an Excel file to import.'))

        # Read Excel file
        df = self._read_excel_file()

        # Check if employee code column exists
        test = df.columns
        if self.employee_code_column not in df.columns:
            raise UserError(_('Employee code column "%s" not found in Excel file.') % self.employee_code_column)

        results = {
            'updated': 0,
            'created': 0,
            'errors': [],
            'total': len(df)
        }

        for index, row in df.iterrows():
            try:
                employee_code = row.get(self.employee_code_column)
                if pd.isna(employee_code) or not employee_code:
                    results['errors'].append(_('Row %d: Missing employee code') % (index + 2))
                    continue

                # Search for existing employee
                employee = self.env['hr.employee'].search([('employee_code', '=', str(employee_code))], limit=1)

                # Prepare employee data
                employee_data = self._prepare_employee_data(row)

                if employee:
                    if self.update_existing:
                        employee.write(employee_data)
                        results['updated'] += 1
                    else:
                        results['errors'].append(_('Row %d: Employee %s already exists') % (index + 2, employee_code))
                else:
                    if self.create_new:
                        employee_data['employee_id'] = str(employee_code)
                        self.env['hr.employee'].create(employee_data)
                        results['created'] += 1
                    else:
                        results['errors'].append(_('Row %d: Employee %s not found') % (index + 2, employee_code))

            except Exception as e:
                results['errors'].append(_('Row %d: %s') % (index + 2, str(e)))

        # Generate results HTML
        self.import_results = self._generate_results_html(results)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'employee.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'show_results': True}
        }

    def _prepare_employee_data(self, row):
        """Prepare employee data from Excel row"""
        data = {}

        # Name
        if self.name_column and self.name_column in row:
            name = row.get(self.name_column)
            if not pd.isna(name):
                data['name'] = str(name).strip()

        # Email
        if self.email_column and self.email_column in row:
            email = row.get(self.email_column)
            if not pd.isna(email):
                data['work_email'] = str(email).strip()

        # Phone
        if self.phone_column and self.phone_column in row:
            phone = row.get(self.phone_column)
            if not pd.isna(phone):
                data['work_phone'] = str(phone).strip()

        # # Department
        # if self.department_column and self.department_column in row:
        #     dept_name = row.get(self.department_column)
        #     if not pd.isna(dept_name):
        #         data['department_id'] = self._get_or_create_department(str(dept_name).strip())
        #
        # # Job Title
        # if self.job_title_column and self.job_title_column in row:
        #     job_title = row.get(self.job_title_column)
        #     if not pd.isna(job_title):
        #         data['job_id'] = self._get_or_create_job(str(job_title).strip())

        # Work Location
        if self.work_location_column and self.work_location_column in row:
            location = row.get(self.work_location_column)
            if not pd.isna(location):
                data['work_location_id'] = self._get_or_create_work_location(str(location).strip())

        # Birthday
        if self.birthday_column and self.birthday_column in row:
            birthday = self._parse_date(row.get(self.birthday_column))
            if birthday:
                data['birthday'] = birthday

        # Gender
        if self.gender_column and self.gender_column in row:
            data['gender'] = self._parse_gender(row.get(self.gender_column))

        # Marital Status
        if self.marital_column and self.marital_column in row:
            data['marital'] = self._parse_marital(row.get(self.marital_column))

        # Identification
        if self.identification_column and self.identification_column in row:
            identification = row.get(self.identification_column)
            if not pd.isna(identification):
                data['identification_id'] = str(identification).strip()

        # Address
        if self.address_column and self.address_column in row:
            address = row.get(self.address_column)
            if not pd.isna(address):
                data['private_street'] = str(address).strip()

        # Hire date
        if self.hire_date_column and self.hire_date_column in row:
            hire_date = self._parse_date(row.get(self.hire_date_column))
            if hire_date:
                data['hire_date'] = hire_date

        return data

    def _get_or_create_work_location(self, location_name):
        """Get or create work location"""
        if not location_name:
            return False

        # This is a simplified version, you might want to use hr_work_location module
        return False

    def _generate_results_html(self, results):
        """Generate HTML results"""
        html = f"""
        <div class="alert alert-info">
            <h4>Import Results</h4>
            <ul>
                <li><strong>Total Records:</strong> {results['total']}</li>
                <li><strong>Created:</strong> {results['created']}</li>
                <li><strong>Updated:</strong> {results['updated']}</li>
                <li><strong>Errors:</strong> {len(results['errors'])}</li>
            </ul>
        </div>
        """

        if results['errors']:
            html += "<div class='alert alert-warning'><h5>Errors:</h5><ul>"
            for error in results['errors'][:10]:  # Show only first 10 errors
                html += f"<li>{error}</li>"
            if len(results['errors']) > 10:
                html += f"<li>... and {len(results['errors']) - 10} more errors</li>"
            html += "</ul></div>"

        return html