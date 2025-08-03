# HR Attendance Overtime Management

## 📝 Description

Advanced overtime calculation module for Odoo 17 HR Attendance system. This module automatically calculates various types of overtime based on work schedules and attendance records, specifically designed for Vietnamese work culture.

## ✨ Features

### 🕐 Multiple Overtime Types
- **Early Overtime**: When arriving 1+ hour before work start (entire duration from check-in to work start)
- **Regular Overtime**: After work hours, before 18:00 (150% rate)
- **Evening Overtime**: 18:00 - 21:00 (150% rate)  
- **Night Overtime**: After 21:00 (200% rate)
- **Holiday Overtime**: Rest days/holidays (200-300% rate)

### 🔄 Smart Rounding Rules
- **0-24 minutes**: Round down to 0
- **25-44 minutes**: Round to 0.5 hours
- **45-60 minutes**: Round up to 1 hour

### 🏢 Department Exclusions
- Office department employees ("Văn phòng")
- Security department employees ("Bảo vệ") 

### 📋 Additional Features
- **Discharge Shift (Xả ca)**: Mark shifts as unpaid
- **Automatic calculation**: On attendance create/update
- **Comprehensive reporting**: Multiple view types
- **Vietnam timezone support**: Asia/Ho_Chi_Minh

## 🚀 Installation

1. Copy the module to your Odoo addons directory
2. Update apps list: `Settings > Apps > Update Apps List`
3. Search for "HR Attendance Overtime Management"
4. Click **Install**

## ⚙️ Configuration

### Prerequisites
1. **HR Attendance** module must be installed
2. **Employees** must have contracts
3. **Contracts** must have work calendars configured

### Setup Steps
1. Go to `HR > Employees > Employees`
2. Ensure each employee has a contract with work calendar
3. Overtime will be calculated automatically based on attendance

## 📊 Usage

### Views Available

#### 📋 Tree View
- Shows all overtime fields in attendance list
- Color-coded by overtime type
- Optional columns (can hide/show)

#### 📝 Form View  
- Detailed overtime breakdown
- All fields are computed and readonly
- Tooltips explain each overtime type

#### 🔍 Search & Filters
- Filter by overtime type
- Filter discharge shifts (xả ca)
- Group by various criteria

#### 📈 Reporting Views
- **Pivot View**: Cross-tab analysis
- **Graph View**: Trend charts
- **Calendar View**: Overtime calendar
- **Kanban View**: Card-based mobile view

### 📊 Overtime Analysis Menu
Navigate to: `HR > Attendance > Overtime Analysis`

## 🔧 Technical Details

### Dependencies
```python
'depends': [
    'hr_attendance',
    'hr_contract', 
    'resource',
]
```

### Key Models
- Extends `hr.attendance` model
- Computed fields with `store=True` for performance
- Automatic calculation triggers

### Database Fields Added
```python
overtime_hours          # Total overtime (Float)
overtime_early          # Early overtime (Float) 
overtime_regular        # Regular overtime (Float)
overtime_evening        # Evening overtime (Float)
overtime_night          # Night overtime (Float)
overtime_holiday        # Holiday overtime (Float)
is_discharge_shift      # Discharge shift flag (Boolean)
```

## 🔒 Security

### Access Rights
- **Users**: Read access to attendance records
- **HR Officers**: Read/Write access  
- **HR Managers**: Full access including delete

## 🌏 Localization

### Vietnam Specific
- Timezone: Asia/Ho_Chi_Minh
- Work culture considerations
- Department name matching in Vietnamese

## 🐛 Troubleshooting

### Common Issues

1. **Overtime not calculating**
   - Check employee has contract
   - Check contract has work calendar
   - Verify department names

2. **Wrong timezone calculations**
   - Set user timezone to Asia/Ho_Chi_Minh
   - Check work calendar timezone settings

3. **Performance issues**
   - Fields are stored for performance
   - Recompute if needed: Developer mode > Recompute

## 📚 Example Scenarios

### Scenario 1: Regular Day
- **Work Schedule**: 8:00 - 17:00
- **Attendance**: 8:00 - 19:30
- **Result**: 
  - Regular OT: 1 hour (17:00-18:00)
  - Evening OT: 1.5 hours (18:00-19:30)

### Scenario 2: Early Arrival
- **Work Schedule**: 8:00 - 17:00  
- **Attendance**: 6:30 - 17:00
- **Result**: 
  - Early OT: 1.5 hours (6:30-8:00, because 6:30 < 7:00)

### Scenario 3: Holiday Work
- **Work Schedule**: Rest day
- **Attendance**: 9:00 - 17:00
- **Result**: 
  - Holiday OT: 8 hours (entire duration)

## 📞 Support

For support and customization:
- Check Odoo logs for errors
- Enable developer mode for debugging
- Contact your system administrator

## 📄 License

LGPL-3 License

## 👥 Author

Your Company - https://www.yourcompany.com

---

**Version**: 17.0.1.0.0  
**Compatible**: Odoo 17.0  
**Last Updated**: 2025