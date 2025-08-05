# Workday Automation

An automated form filling system for Workday job applications that streamlines the application process by automatically filling out forms with your personal information.

## Features

- **Automated Form Filling**: Automatically fills out Workday job application forms
- **Multi-Page Support**: Handles multiple application pages (My Information, Experience, Voluntary Disclosures, etc.)
- **Smart Field Detection**: Uses multiple selector strategies (id, data-automation-id, name attributes)
- **Date Field Handling**: Properly handles individual date components (month, day, year)
- **Dropdown Support**: Handles various dropdown types including button-based and searchable dropdowns
- **Radio Button Support**: Automatically selects appropriate radio button options
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Form Extraction**: Extracts form structure and saves to JSON for analysis

## Prerequisites

- Python 3.7+
- Playwright browser automation library
- Chrome/Chromium browser

## Installation

```bash
git clone https://github.com/lakshinkhurana/workday-automation.git
cd workday-automation
pip install playwright python-dotenv
playwright install chromium
```

## Configuration

Create a `.env` file in the project root with your personal information.

## Usage

```bash
python run_automation.py
```

## Project Structure

```
workday-automation/
├── .env
├── base_exceptions.py
├── extraction.py
├── filling.py
├── mapping.py
├── run_automation.py
├── workday_forms_complete.json
```

## How It Works

1. Navigate to the job URL
2. Log in / create account using `.env` data
3. Fill in all required form pages (info, experience, etc.)
4. Submit the application

## Supported Field Types

- Text fields, date pickers, dropdowns, radio buttons, checkboxes

## Field Detection Strategy

- ID, data-automation-id, name, and partial matches

## Form Extraction

- JSON output including all field metadata

## Troubleshooting

- **Field not detected**: Check for DOM changes
- **Login failed**: Validate `.env` credentials
- **Playwright errors**: Run `playwright install` again

## Legal and Ethical Use

Use only for educational/personal purposes. Respect company application rules and website terms.

## License

Licensed under a non-commercial license. See LICENSE file.