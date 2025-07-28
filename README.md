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

1. **Clone the repository:**
   ```bash
   git clone https://github.com/lakshinkhurana/workday-automation.git
   cd workday-automation
   ```

2. **Install required dependencies:**
   ```bash
   pip install playwright python-dotenv
   ```

3. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

## Configuration

Create a `.env` file in the project root with your personal information:

```env
<<<<<<< HEAD
# Workday Configuration
=======
>>>>>>> 4cbfa38f73e545223e2a3c564ee64bb194965d8e
WORKDAY_TENANT_URL=https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite
WORKDAY_USERNAME=dummy128mailneeded@gmail.com
WORKDAY_PASSWORD=SecurePassword@123
JOB_URL=https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/US%2C-CA%2C-Santa-Clara/Senior-Systems-Engineer--DriveAV---Autonomous-Vehicles_JR2000493/apply/applyManually?locationHierarchy1=2fcb99c455831013ea52fb338f2932d8
<<<<<<< HEAD
RESUME_PATH=C:/Users/YourName/Downloads/your_resume.pdf
=======
RESUME_PATH=Lin Mei_Experiened Level Software.pdf
>>>>>>> 4cbfa38f73e545223e2a3c564ee64bb194965d8e
WORKDAY_END_URL=https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/jobTasks/completed/application

# Registration Configuration
CREATE_ACCOUNT_MODE=true
<<<<<<< HEAD
REGISTRATION_FIRST_NAME=Your_First_Name
REGISTRATION_LAST_NAME=Your_Last_Name
JOB_BOARD=Indeed
REGISTRATION_EMAIL=your_email@gmail.com
REGISTRATION_PASSWORD=SecurePassword@123
REGISTRATION_PHONE=123-456-7890

# Personal Information
FULL_NAME=Your Full Name
LOCATION=Your City, State
COUNTRY=United States Of America
GITHUB_URL=https://github.com/yourusername
CURRENT_POSITION=Your Current Position
YEARS_EXPERIENCE=5+

# Education
EDUCATION_MASTERS=Master of Science in Computer Science - University Name, City, State
EDUCATION_BACHELORS=Bachelor of Engineering in Computer Science - University Name, City, State

# Current Employment
CURRENT_COMPANY=Your Current Company
CURRENT_ROLE=Your Current Role
EMPLOYMENT_PERIOD=Jan 2020 - Present

# Previous Employment
PREVIOUS_COMPANY=Your Previous Company
PREVIOUS_ROLE=Your Previous Role
PREVIOUS_PERIOD=Jan 2018 - Dec 2019

# Skills Summary
PRIMARY_SKILLS=Python, JavaScript, Java, SQL, HTML5, CSS3
FRAMEWORKS=Django, React, Node.js, Express
CLOUD_PLATFORMS=AWS, Azure, Google Cloud
DATABASES=PostgreSQL, MySQL, MongoDB
TESTING_FRAMEWORKS=Jest, Pytest, Selenium

# Personal Preferences
=======
REGISTRATION_FIRST_NAME=Lin
REGISTRATION_LAST_NAME=Mei
JOB_BOARD=Indeed
REGISTRATION_EMAIL=lmei53854@gmail.com
REGISTRATION_PASSWORD=SecurePassword@123
REGISTRATION_PHONE=650-450-8692

# Personal Information from CV
FULL_NAME=Lin Mei
LOCATION=California, USA
COUNTRY = United States Of America
GITHUB_URL=https://github.com/navinAdhe
CURRENT_POSITION=Software Engineer
YEARS_EXPERIENCE=7+

# Education
EDUCATION_MASTERS=Master of Science in Computer Science - University of California, Davis, California, USA
EDUCATION_BACHELORS=Bachelor of Engineering in Computer Science - University of Pune, Maharashtra, India

# Current Employment
CURRENT_COMPANY=OSIsoft LLC, San Francisco Bay Area - USA
CURRENT_ROLE=Sr. Software Developer
EMPLOYMENT_PERIOD=Aug 2023 - Present

# Previous Employment
PREVIOUS_COMPANY=Cybage Software, Pune - India
PREVIOUS_ROLE=Software Engineer
PREVIOUS_PERIOD=Feb 2016 - Jun 2017

# Skills Summary
PRIMARY_SKILLS=C#, TypeScript, Java, JavaScript, SQL, HTML5, CSS3, Python
FRAMEWORKS=.NET Core, Angular 2+, RxJS, Entity Framework, React, Redux, Bootstrap 4
CLOUD_PLATFORMS=Microsoft Azure, Azure Functions, App Services, Blob Storage
DATABASES=SQL Server, Stored Procedures, Triggers, Functions
TESTING_FRAMEWORKS=Jasmine, Karma, Cypress, Appium, Selenium
>>>>>>> 4cbfa38f73e545223e2a3c564ee64bb194965d8e
DISABILITY_STATUS=I do not wish to answer
```

**Important**: Update the `WORKDAY_TENANT_URL` with the specific company's Workday careers page URL.

## Usage

### Basic Usage

Run the main automation script:
```bash
python main.py
```

### Direct Form Filling

For direct form filling on an already opened page:
```bash
python direct_form_filler.py
```

## Project Structure

```
workday-automation/
├── .gitignore
<<<<<<< HEAD
├── main.py                    # Main automation flow
├── direct_form_filler.py      # Direct form filling logic
├── config_manager.py          # Configuration management
├── resume_fill.py             # Resume handling logic
├── performance_monitor.py     # Performance monitoring
=======
├── main.py                     # Main automation flow
├── direct_form_filler.py       # Direct form filling logic
├── config_manager.py       
├── resume_fill.py
├── performance_monitor.py       
>>>>>>> 4cbfa38f73e545223e2a3c564ee64bb194965d8e
├── .env                       # Environment variables (create this)
├── workday_forms_complete.json # Extracted form data
├── README.md                  # This file
└── LICENSE                    # License file
```

## How It Works

The automation system follows this workflow:

1. **Navigation**: Automatically navigates to the job posting page
2. **Job Selection**: Finds and clicks on job title links
3. **Application Flow**: Handles the "Apply" → "Apply Manually" flow
4. **Account Creation**: Creates account if needed using provided information
5. **Form Filling**: Fills out all application forms across multiple pages:
   - My Information (personal details, contact info)
   - My Experience (work history, skills)
   - Application Questions (job-specific questions)
   - Voluntary Disclosures (EEO information)
   - Self Identify (disability status)
6. **Form Submission**: Submits completed forms

## Supported Field Types

The system can handle various form field types:

- **Text Fields**: Name, email, phone, address, etc.
- **Date Fields**: Individual month/day/year spinbutton inputs
- **Dropdown Fields**: Select dropdowns and searchable dropdowns
- **Radio Buttons**: Yes/No questions, multiple choice
- **Checkboxes**: Terms acceptance, preferences
- **Textarea Fields**: Long text responses

## Field Detection Strategy

The system uses multiple strategies to find form fields:

1. **ID Attribute**: `input[id="fieldName"]`
2. **Data Automation ID**: `input[data-automation-id="fieldName"]`
3. **Name Attribute**: `input[name="fieldName"]`
4. **Partial Matching**: `input[id*="fieldName"]`

## Form Structure Extraction

The system extracts form structure and saves it to `workday_forms_complete.json` including:

- Field labels and IDs
- Field types (text, select, radio, checkbox)
- Required field indicators
- Available options for dropdowns
- Page metadata

## Logging and Debugging

Enable detailed logging by checking the console output. The system provides:

- Field detection attempts
- Successful/failed form fills
- Selector strategies used
- Error messages and troubleshooting info

## Important Considerations

- **Rate Limiting**: The system includes delays to avoid overwhelming servers
- **Browser Visibility**: Runs in non-headless mode for monitoring
- **Manual Intervention**: Some complex fields may require manual completion
- **Company-Specific**: May need adjustments for different Workday implementations

## Privacy and Security

- All personal information is stored locally in the `.env` file
- No data is transmitted to external servers except the target Workday site
- Use responsibly and in accordance with company application policies

## Legal and Ethical Use

This project is for educational and personal use only. Please ensure compliance with:

- Website terms of service
- Company application policies
- Applicable laws and regulations

## License

This project is licensed under a Non-Commercial License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is provided for educational purposes only. Users are responsible for:

- Ensuring compliance with website terms of service
- Providing accurate information in applications
- Using the tool ethically and responsibly
- Respecting rate limits and server resources

The authors are not responsible for any misuse of this tool or consequences arising from its use.

## Troubleshooting

Common issues and solutions:

- **Fields Not Found**: Check if field IDs have changed on the website
- **Slow Performance**: Increase delays in the code if needed
- **Login Issues**: Ensure correct credentials in `.env` file
- **Browser Crashes**: Update Playwright and browser versions

### Debug Steps

1. Check the console output for detailed error messages
2. Verify your `.env` configuration
3. Ensure the Workday URL is correct and accessible
4. Test with a simple job application first

**Remember**: Always use this tool responsibly and in compliance with applicable terms of service and policies.
