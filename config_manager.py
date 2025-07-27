#!/usr/bin/env python3
"""
Configuration Manager for Workday Page Automation
Author: Web Automation Engineer
Date: 2025-01-26
Description: 
Handles configuration loading from JSON files and environment variables,
validation, default values, and automation mode settings.
Requirements: 4.1, 4.2, 4.3, 4.4
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class AutomationModeConfig:
    """Configuration for different automation modes"""
    headless: bool = True
    debug: bool = False
    slow_motion: int = 0  # milliseconds
    timeout: int = 30000  # milliseconds
    screenshot_on_failure: bool = True
    video_recording: bool = False
    trace_recording: bool = False

@dataclass
class PageProcessorConfig:
    """Configuration for page-specific processors"""
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    navigation_selector: str = ""
    page_timeout: int = 30000
    retry_attempts: int = 3
    skip_on_error: bool = False

@dataclass
class FormElementConfig:
    """Configuration for form elements matching the JSON structure"""
    label: str = ""
    id_of_input_component: str = ""
    required: bool = False
    type_of_input: str = "text"
    options: List[str] = field(default_factory=list)
    user_data_select_values: List[str] = field(default_factory=list)

@dataclass
class AutomationConfig:
    """Main automation configuration"""
    max_retries: int = 3
    page_timeout: int = 30000
    navigation_delay: int = 2000
    element_wait_timeout: int = 10000
    form_fill_delay: int = 100
    enable_progress_tracking: bool = True
    save_automation_state: bool = True
    log_level: str = "INFO"
    enable_performance_monitoring: bool = True
    performance_log_interval: int = 30

@dataclass
class WorkdayConfig:
    """Workday-specific configuration"""
    tenant_url: str = ""
    job_url: str = ""
    create_account_mode: bool = True
    resume_path: str = ""
    
    # Account creation fields
    registration_first_name: str = ""
    registration_last_name: str = ""
    registration_email: str = ""
    registration_password: str = ""
    registration_phone: str = ""
    
    # Personal information
    full_name: str = ""
    location: str = ""
    country: str = ""
    github_url: str = ""
    current_position: str = ""
    years_experience: str = ""
    job_board: str = ""
    
    # Education
    education_masters_school: str = ""
    education_masters_degree: str = ""
    education_masters_specialisation: str = ""
    masters_start: str = ""
    masters_end: str = ""
    education_bachelors_school: str = ""
    education_bachelors_degree: str = ""
    education_bachelors_specialisation: str = ""
    bachelors_start: str = ""
    bachelors_end: str = ""
    
    # Employment
    current_company: str = ""
    current_role: str = ""
    employment_period: str = ""
    previous_company: str = ""
    previous_role: str = ""
    previous_period: str = ""
    
    # Skills
    primary_skills: str = ""
    frameworks: str = ""
    cloud_platforms: str = ""
    databases: str = ""
    testing_frameworks: str = ""
    
    # Other information
    veteran_status: str = ""
    gender: str = ""
    ethnicity: str = ""

@dataclass
class WorkdayPageAutomationConfig:
    """Complete configuration for Workday Page Automation"""
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    automation_mode: AutomationModeConfig = field(default_factory=AutomationModeConfig)
    workday: WorkdayConfig = field(default_factory=WorkdayConfig)
    page_processors: Dict[str, PageProcessorConfig] = field(default_factory=dict)
    form_elements: List[FormElementConfig] = field(default_factory=list)

class ConfigurationManager:
    """
    Manages configuration loading, validation, and default values
    Requirements: 4.1, 4.2, 4.3, 4.4
    """
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(f"{__name__}.ConfigurationManager")
        self._config: Optional[WorkdayPageAutomationConfig] = None
        
        # Default configuration file paths
        self.main_config_file = self.config_dir / "automation_config.json"
        self.form_elements_file = self.config_dir / "form_elements.json"
        self.page_processors_file = self.config_dir / "page_processors.json"
        
    def load_configuration(self, config_file: Optional[str] = None) -> WorkdayPageAutomationConfig:
        """
        Load configuration from JSON files and environment variables
        Requirement: 4.1 - Create configuration loading from JSON files and environment variables
        """
        self.logger.info("Loading configuration from JSON files and environment variables")
        
        try:
            # Start with default configuration
            config = WorkdayPageAutomationConfig()
            
            # Load from JSON files if they exist
            if config_file:
                config = self._load_from_json_file(config_file)
            else:
                config = self._load_from_default_files()
            
            # Override with environment variables
            config = self._load_from_environment(config)
            
            # Validate configuration
            self._validate_configuration(config)
            
            # Apply default values where needed
            config = self._apply_default_values(config)
            
            self._config = config
            self.logger.info("Configuration loaded successfully")
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # Return default configuration as fallback
            return self._get_default_configuration()
    
    def _load_from_json_file(self, config_file: str) -> WorkdayPageAutomationConfig:
        """Load configuration from a single JSON file"""
        config_path = Path(config_file)
        
        if not config_path.exists():
            self.logger.warning(f"Configuration file not found: {config_file}, using defaults")
            return WorkdayPageAutomationConfig()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return self._parse_config_data(config_data)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file {config_file}: {e}")
            return WorkdayPageAutomationConfig()
        except Exception as e:
            self.logger.error(f"Error reading configuration file {config_file}: {e}")
            return WorkdayPageAutomationConfig()
    
    def _load_from_default_files(self) -> WorkdayPageAutomationConfig:
        """Load configuration from default configuration files"""
        config = WorkdayPageAutomationConfig()
        
        # Load main automation configuration
        if self.main_config_file.exists():
            try:
                with open(self.main_config_file, 'r', encoding='utf-8') as f:
                    main_config_data = json.load(f)
                config = self._parse_config_data(main_config_data)
            except Exception as e:
                self.logger.warning(f"Error loading main config file: {e}")
        
        # Load form elements configuration
        if self.form_elements_file.exists():
            try:
                with open(self.form_elements_file, 'r', encoding='utf-8') as f:
                    form_elements_data = json.load(f)
                config.form_elements = self._parse_form_elements(form_elements_data)
            except Exception as e:
                self.logger.warning(f"Error loading form elements config: {e}")
        
        # Load page processors configuration
        if self.page_processors_file.exists():
            try:
                with open(self.page_processors_file, 'r', encoding='utf-8') as f:
                    page_processors_data = json.load(f)
                config.page_processors = self._parse_page_processors(page_processors_data)
            except Exception as e:
                self.logger.warning(f"Error loading page processors config: {e}")
        
        return config
    
    def _parse_config_data(self, config_data: Dict[str, Any]) -> WorkdayPageAutomationConfig:
        """Parse configuration data from JSON"""
        config = WorkdayPageAutomationConfig()
        
        # Parse automation configuration
        if 'automation' in config_data:
            automation_data = config_data['automation']
            config.automation = AutomationConfig(**{
                k: v for k, v in automation_data.items() 
                if k in AutomationConfig.__dataclass_fields__
            })
        
        # Parse automation mode configuration
        if 'automation_mode' in config_data:
            mode_data = config_data['automation_mode']
            config.automation_mode = AutomationModeConfig(**{
                k: v for k, v in mode_data.items() 
                if k in AutomationModeConfig.__dataclass_fields__
            })
        
        # Parse workday configuration
        if 'workday' in config_data:
            workday_data = config_data['workday']
            config.workday = WorkdayConfig(**{
                k: v for k, v in workday_data.items() 
                if k in WorkdayConfig.__dataclass_fields__
            })
        
        # Parse page processors
        if 'page_processors' in config_data:
            config.page_processors = self._parse_page_processors(config_data['page_processors'])
        
        # Parse form elements
        if 'form_elements' in config_data:
            config.form_elements = self._parse_form_elements(config_data['form_elements'])
        
        return config
    
    def _parse_form_elements(self, form_elements_data: Union[List[Dict], Dict]) -> List[FormElementConfig]:
        """Parse form elements configuration"""
        form_elements = []
        
        if isinstance(form_elements_data, list):
            elements_list = form_elements_data
        elif isinstance(form_elements_data, dict) and 'form_elements' in form_elements_data:
            elements_list = form_elements_data['form_elements']
        else:
            return form_elements
        
        for element_data in elements_list:
            try:
                element = FormElementConfig(**{
                    k: v for k, v in element_data.items() 
                    if k in FormElementConfig.__dataclass_fields__
                })
                form_elements.append(element)
            except Exception as e:
                self.logger.warning(f"Error parsing form element: {e}")
        
        return form_elements
    
    def _parse_page_processors(self, processors_data: Dict[str, Any]) -> Dict[str, PageProcessorConfig]:
        """Parse page processors configuration"""
        page_processors = {}
        
        for page_name, processor_data in processors_data.items():
            try:
                processor_config = PageProcessorConfig(**{
                    k: v for k, v in processor_data.items() 
                    if k in PageProcessorConfig.__dataclass_fields__
                })
                page_processors[page_name] = processor_config
            except Exception as e:
                self.logger.warning(f"Error parsing page processor config for {page_name}: {e}")
        
        return page_processors
    
    def _load_from_environment(self, config: WorkdayPageAutomationConfig) -> WorkdayPageAutomationConfig:
        """
        Override configuration with environment variables
        Requirement: 4.1 - Create configuration loading from JSON files and environment variables
        """
        # Automation mode settings
        config.automation_mode.headless = self._get_env_bool('AUTOMATION_HEADLESS', config.automation_mode.headless)
        config.automation_mode.debug = self._get_env_bool('AUTOMATION_DEBUG', config.automation_mode.debug)
        config.automation_mode.slow_motion = self._get_env_int('AUTOMATION_SLOW_MOTION', config.automation_mode.slow_motion)
        config.automation_mode.timeout = self._get_env_int('AUTOMATION_TIMEOUT', config.automation_mode.timeout)
        config.automation_mode.screenshot_on_failure = self._get_env_bool('AUTOMATION_SCREENSHOT_ON_FAILURE', config.automation_mode.screenshot_on_failure)
        config.automation_mode.video_recording = self._get_env_bool('AUTOMATION_VIDEO_RECORDING', config.automation_mode.video_recording)
        config.automation_mode.trace_recording = self._get_env_bool('AUTOMATION_TRACE_RECORDING', config.automation_mode.trace_recording)
        
        # Automation settings
        config.automation.max_retries = self._get_env_int('AUTOMATION_MAX_RETRIES', config.automation.max_retries)
        config.automation.page_timeout = self._get_env_int('AUTOMATION_PAGE_TIMEOUT', config.automation.page_timeout)
        config.automation.navigation_delay = self._get_env_int('AUTOMATION_NAVIGATION_DELAY', config.automation.navigation_delay)
        config.automation.log_level = os.getenv('AUTOMATION_LOG_LEVEL', config.automation.log_level)
        
        # Workday settings
        config.workday.tenant_url = os.getenv('WORKDAY_TENANT_URL', config.workday.tenant_url)
        config.workday.job_url = os.getenv('JOB_URL', config.workday.job_url)
        config.workday.create_account_mode = self._get_env_bool('CREATE_ACCOUNT_MODE', config.workday.create_account_mode)
        config.workday.resume_path = os.getenv('RESUME_PATH', config.workday.resume_path)
        
        # Registration information
        config.workday.registration_first_name = os.getenv('REGISTRATION_FIRST_NAME', config.workday.registration_first_name)
        config.workday.registration_last_name = os.getenv('REGISTRATION_LAST_NAME', config.workday.registration_last_name)
        config.workday.registration_email = os.getenv('REGISTRATION_EMAIL', config.workday.registration_email)
        config.workday.registration_password = os.getenv('REGISTRATION_PASSWORD', config.workday.registration_password)
        config.workday.registration_phone = os.getenv('REGISTRATION_PHONE', config.workday.registration_phone)
        
        # Personal information
        config.workday.full_name = os.getenv('FULL_NAME', config.workday.full_name)
        config.workday.location = os.getenv('LOCATION', config.workday.location)
        config.workday.country = os.getenv('COUNTRY', config.workday.country)
        config.workday.github_url = os.getenv('GITHUB_URL', config.workday.github_url)
        config.workday.current_position = os.getenv('CURRENT_POSITION', config.workday.current_position)
        config.workday.years_experience = os.getenv('YEARS_EXPERIENCE', config.workday.years_experience)
        config.workday.job_board = os.getenv('JOB_BOARD', config.workday.job_board)
        
        # Education
        config.workday.education_masters_school = os.getenv('EDUCATION_MASTERS_SCHOOL', config.workday.education_masters_school)
        config.workday.education_masters_degree = os.getenv('EDUCATION_MASTERS_DEGREE', config.workday.education_masters_degree)
        config.workday.education_masters_specialisation = os.getenv('EDUCATION_MASTERS_SPECIALISATION', config.workday.education_masters_specialisation)
        config.workday.masters_start = os.getenv('MASTERS_START', config.workday.masters_start)
        config.workday.masters_end = os.getenv('MASTERS_END', config.workday.masters_end)
        config.workday.education_bachelors_school = os.getenv('EDUCATION_BACHELORS_SCHOOL', config.workday.education_bachelors_school)
        config.workday.education_bachelors_degree = os.getenv('EDUCATION_BACHELORS_DEGREE', config.workday.education_bachelors_degree)
        config.workday.education_bachelors_specialisation = os.getenv('EDUCATION_BACHELORS_SPECIALISATION', config.workday.education_bachelors_specialisation)
        config.workday.bachelors_start = os.getenv('BACHELORS_START', config.workday.bachelors_start)
        config.workday.bachelors_end = os.getenv('BACHELORS_END', config.workday.bachelors_end)
        
        # Employment
        config.workday.current_company = os.getenv('CURRENT_COMPANY', config.workday.current_company)
        config.workday.current_role = os.getenv('CURRENT_ROLE', config.workday.current_role)
        config.workday.employment_period = os.getenv('EMPLOYMENT_PERIOD', config.workday.employment_period)
        config.workday.previous_company = os.getenv('PREVIOUS_COMPANY', config.workday.previous_company)
        config.workday.previous_role = os.getenv('PREVIOUS_ROLE', config.workday.previous_role)
        config.workday.previous_period = os.getenv('PREVIOUS_PERIOD', config.workday.previous_period)
        
        # Skills
        config.workday.primary_skills = os.getenv('PRIMARY_SKILLS', config.workday.primary_skills)
        config.workday.frameworks = os.getenv('FRAMEWORKS', config.workday.frameworks)
        config.workday.cloud_platforms = os.getenv('CLOUD_PLATFORMS', config.workday.cloud_platforms)
        config.workday.databases = os.getenv('DATABASES', config.workday.databases)
        config.workday.testing_frameworks = os.getenv('TESTING_FRAMEWORKS', config.workday.testing_frameworks)
        
        # Other information
        config.workday.veteran_status = os.getenv('VETERAN_STATUS', config.workday.veteran_status)
        config.workday.gender = os.getenv('GENDER', config.workday.gender)
        config.workday.ethnicity = os.getenv('ETHNICITY', config.workday.ethnicity)
        
        return config
    
    def _validate_configuration(self, config: WorkdayPageAutomationConfig) -> None:
        """
        Validate configuration and raise errors for critical missing values
        Requirement: 4.2 - Implement configuration validation and default value handling
        """
        errors = []
        
        # Validate required Workday settings
        if not config.workday.tenant_url:
            errors.append("WORKDAY_TENANT_URL is required")
        
        if config.workday.create_account_mode:
            if not config.workday.registration_email:
                errors.append("REGISTRATION_EMAIL is required when CREATE_ACCOUNT_MODE is true")
            if not config.workday.registration_password:
                errors.append("REGISTRATION_PASSWORD is required when CREATE_ACCOUNT_MODE is true")
            if not config.workday.registration_first_name:
                errors.append("REGISTRATION_FIRST_NAME is required when CREATE_ACCOUNT_MODE is true")
            if not config.workday.registration_last_name:
                errors.append("REGISTRATION_LAST_NAME is required when CREATE_ACCOUNT_MODE is true")
        
        # Validate automation mode settings
        if config.automation_mode.timeout < 1000:
            errors.append("AUTOMATION_TIMEOUT must be at least 1000ms")
        
        if config.automation.max_retries < 0:
            errors.append("AUTOMATION_MAX_RETRIES must be non-negative")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if config.automation.log_level not in valid_log_levels:
            errors.append(f"AUTOMATION_LOG_LEVEL must be one of: {', '.join(valid_log_levels)}")
        
        if errors:
            error_message = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            self.logger.error(error_message)
            raise ValueError(error_message)
        
        self.logger.info("Configuration validation passed")
    
    def _apply_default_values(self, config: WorkdayPageAutomationConfig) -> WorkdayPageAutomationConfig:
        """
        Apply default values where configuration is missing
        Requirement: 4.2 - Implement configuration validation and default value handling
        """
        # Apply default page processors if none configured
        if not config.page_processors:
            config.page_processors = self._get_default_page_processors()
        
        # Apply default form elements if none configured
        if not config.form_elements:
            config.form_elements = self._get_default_form_elements()
        
        # Ensure automation mode has sensible defaults
        if config.automation_mode.timeout == 0:
            config.automation_mode.timeout = 30000
        
        # Set default country if not specified
        if not config.workday.country and config.workday.location:
            if 'usa' in config.workday.location.lower() or 'united states' in config.workday.location.lower():
                config.workday.country = 'United States'
        
        self.logger.info("Default values applied to configuration")
        return config
    
    def _get_default_page_processors(self) -> Dict[str, PageProcessorConfig]:
        """Get default page processor configurations"""
        return {
            "login": PageProcessorConfig(
                required_fields=["email", "password"],
                navigation_selector="button:has-text('Sign In'), button:has-text('Next')",
                page_timeout=15000,
                retry_attempts=2
            ),
            "my_information": PageProcessorConfig(
                required_fields=["firstName", "lastName", "email", "phone"],
                optional_fields=["country", "source"],
                navigation_selector="button:has-text('Continue'), button:has-text('Next')",
                page_timeout=20000,
                retry_attempts=3
            ),
            "job_application": PageProcessorConfig(
                required_fields=["workExperience", "education"],
                optional_fields=["skills", "github", "linkedin"],
                navigation_selector="button:has-text('Continue'), button:has-text('Next')",
                page_timeout=30000,
                retry_attempts=3
            ),
            "eeo": PageProcessorConfig(
                required_fields=[],
                optional_fields=["gender", "ethnicity", "veteran_status"],
                navigation_selector="button:has-text('Continue'), button:has-text('Next')",
                page_timeout=15000,
                retry_attempts=2,
                skip_on_error=True
            ),
            "review": PageProcessorConfig(
                required_fields=["terms_acceptance"],
                navigation_selector="button:has-text('Submit'), button:has-text('Apply')",
                page_timeout=20000,
                retry_attempts=2
            )
        }
    
    def _get_default_form_elements(self) -> List[FormElementConfig]:
        """Get default form element configurations"""
        return [
            FormElementConfig(
                label="First Name",
                id_of_input_component="name--legalName--firstName",
                required=True,
                type_of_input="text"
            ),
            FormElementConfig(
                label="Last Name", 
                id_of_input_component="name--legalName--lastName",
                required=True,
                type_of_input="text"
            ),
            FormElementConfig(
                label="Email Address",
                id_of_input_component="email",
                required=True,
                type_of_input="text"
            ),
            FormElementConfig(
                label="Phone Number",
                id_of_input_component="phoneNumber--phoneNumber",
                required=True,
                type_of_input="text"
            ),
            FormElementConfig(
                label="Country",
                id_of_input_component="country--country",
                required=False,
                type_of_input="select",
                options=["United States", "Canada", "United Kingdom"],
                user_data_select_values=["United States"]
            ),
            FormElementConfig(
                label="How did you hear about this position?",
                id_of_input_component="source--source",
                required=False,
                type_of_input="dropdown",
                options=["Company Website", "LinkedIn", "Indeed", "Referral"],
                user_data_select_values=["LinkedIn"]
            ),
            FormElementConfig(
                label="Have you previously worked for this company?",
                id_of_input_component="candidateIsPreviousWorker",
                required=True,
                type_of_input="radio",
                options=["Yes", "No"],
                user_data_select_values=["No"]
            )
        ]
    
    def _get_default_configuration(self) -> WorkdayPageAutomationConfig:
        """Get a complete default configuration as fallback"""
        config = WorkdayPageAutomationConfig()
        config.page_processors = self._get_default_page_processors()
        config.form_elements = self._get_default_form_elements()
        return config
    
    def _get_env_bool(self, key: str, default: bool) -> bool:
        """Get boolean value from environment variable"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _get_env_int(self, key: str, default: int) -> int:
        """Get integer value from environment variable"""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            self.logger.warning(f"Invalid integer value for {key}, using default: {default}")
            return default
    
    def save_configuration(self, config: WorkdayPageAutomationConfig, config_file: Optional[str] = None) -> bool:
        """Save configuration to JSON file"""
        try:
            if config_file:
                output_file = Path(config_file)
            else:
                output_file = self.main_config_file
            
            # Convert dataclass to dictionary
            config_dict = asdict(config)
            
            # Ensure directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write configuration to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Configuration saved to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False
    
    def get_automation_mode_config(self) -> AutomationModeConfig:
        """
        Get automation mode configuration for different modes (headless, debug, etc.)
        Requirement: 4.3 - Add support for different automation modes (headless, debug, etc.)
        """
        if not self._config:
            self.load_configuration()
        return self._config.automation_mode
    
    def get_page_processor_config(self, page_name: str) -> Optional[PageProcessorConfig]:
        """Get configuration for a specific page processor"""
        if not self._config:
            self.load_configuration()
        return self._config.page_processors.get(page_name)
    
    def get_form_elements_config(self) -> List[FormElementConfig]:
        """Get form elements configuration"""
        if not self._config:
            self.load_configuration()
        return self._config.form_elements
    
    def get_workday_config(self) -> WorkdayConfig:
        """Get Workday-specific configuration"""
        if not self._config:
            self.load_configuration()
        return self._config.workday
    
    def get_automation_config(self) -> AutomationConfig:
        """Get general automation configuration"""
        if not self._config:
            self.load_configuration()
        return self._config.automation
    
    def create_example_configuration_files(self) -> bool:
        """
        Create example configuration files for documentation
        Requirement: 4.4 - Create configuration documentation and example files
        """
        try:
            # Create example main configuration
            example_config = self._get_example_main_config()
            example_config_file = self.config_dir / "automation_config.example.json"
            
            with open(example_config_file, 'w', encoding='utf-8') as f:
                json.dump(example_config, f, indent=2, ensure_ascii=False)
            
            # Create example form elements configuration
            example_form_elements = self._get_example_form_elements_config()
            example_form_elements_file = self.config_dir / "form_elements.example.json"
            
            with open(example_form_elements_file, 'w', encoding='utf-8') as f:
                json.dump(example_form_elements, f, indent=2, ensure_ascii=False)
            
            # Create example page processors configuration
            example_page_processors = self._get_example_page_processors_config()
            example_page_processors_file = self.config_dir / "page_processors.example.json"
            
            with open(example_page_processors_file, 'w', encoding='utf-8') as f:
                json.dump(example_page_processors, f, indent=2, ensure_ascii=False)
            
            self.logger.info("Example configuration files created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create example configuration files: {e}")
            return False
    
    def _get_example_main_config(self) -> Dict[str, Any]:
        """Get example main configuration"""
        return {
            "automation": {
                "max_retries": 3,
                "page_timeout": 30000,
                "navigation_delay": 2000,
                "element_wait_timeout": 10000,
                "form_fill_delay": 100,
                "enable_progress_tracking": True,
                "save_automation_state": True,
                "log_level": "INFO"
            },
            "automation_mode": {
                "headless": True,
                "debug": False,
                "slow_motion": 0,
                "timeout": 30000,
                "screenshot_on_failure": True,
                "video_recording": False,
                "trace_recording": False
            },
            "workday": {
                "tenant_url": "https://company.wd5.myworkdayjobs.com/en-US/ExternalCareerSite",
                "job_url": "https://company.wd5.myworkdayjobs.com/en-US/ExternalCareerSite/job/...",
                "create_account_mode": True,
                "resume_path": "/path/to/resume.pdf",
                "registration_first_name": "John",
                "registration_last_name": "Doe",
                "registration_email": "john.doe@example.com",
                "registration_password": "SecurePassword123",
                "registration_phone": "555-123-4567",
                "full_name": "John Doe",
                "location": "California, USA",
                "country": "United States",
                "github_url": "https://github.com/johndoe",
                "current_position": "Software Engineer",
                "years_experience": "5+",
                "job_board": "LinkedIn"
            }
        }
    
    def _get_example_form_elements_config(self) -> Dict[str, Any]:
        """Get example form elements configuration"""
        return {
            "form_elements": [
                {
                    "label": "First Name",
                    "id_of_input_component": "name--legalName--firstName",
                    "required": True,
                    "type_of_input": "text",
                    "options": [],
                    "user_data_select_values": []
                },
                {
                    "label": "How did you hear about this position?",
                    "id_of_input_component": "source--source",
                    "required": False,
                    "type_of_input": "dropdown",
                    "options": ["Company Website", "LinkedIn", "Indeed", "Referral"],
                    "user_data_select_values": ["LinkedIn"]
                },
                {
                    "label": "Have you previously worked for this company?",
                    "id_of_input_component": "candidateIsPreviousWorker",
                    "required": True,
                    "type_of_input": "radio",
                    "options": ["Yes", "No"],
                    "user_data_select_values": ["No"]
                }
            ]
        }
    
    def _get_example_page_processors_config(self) -> Dict[str, Any]:
        """Get example page processors configuration"""
        return {
            "login": {
                "required_fields": ["email", "password"],
                "optional_fields": [],
                "navigation_selector": "button:has-text('Sign In')",
                "page_timeout": 15000,
                "retry_attempts": 2,
                "skip_on_error": False
            },
            "my_information": {
                "required_fields": ["firstName", "lastName", "email", "phone"],
                "optional_fields": ["country", "source"],
                "navigation_selector": "button:has-text('Continue')",
                "page_timeout": 20000,
                "retry_attempts": 3,
                "skip_on_error": False
            },
            "job_application": {
                "required_fields": ["workExperience", "education"],
                "optional_fields": ["skills", "github", "linkedin"],
                "navigation_selector": "button:has-text('Continue')",
                "page_timeout": 30000,
                "retry_attempts": 3,
                "skip_on_error": False
            },
            "eeo": {
                "required_fields": [],
                "optional_fields": ["gender", "ethnicity", "veteran_status"],
                "navigation_selector": "button:has-text('Continue')",
                "page_timeout": 15000,
                "retry_attempts": 2,
                "skip_on_error": True
            },
            "review": {
                "required_fields": ["terms_acceptance"],
                "optional_fields": [],
                "navigation_selector": "button:has-text('Submit')",
                "page_timeout": 20000,
                "retry_attempts": 2,
                "skip_on_error": False
            }
        }