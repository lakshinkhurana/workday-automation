
"""
mapping.py

This module is responsible for mapping extracted data to internal data representations
and linking them to the appropriate form fields. It prepares the data for the filling process.
"""

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Field mappings connect form field identifiers (IDs, names) to environment variables.
# This is a consolidated and cleaned-up version of the original mappings.
FIELD_MAPPINGS = {
    # My Information page fields
    'name--legalName--firstName': 'REGISTRATION_FIRST_NAME',
    'name--legalName--lastName': 'REGISTRATION_LAST_NAME',
    'email': 'REGISTRATION_EMAIL',
    'phoneNumber--phoneNumber': 'REGISTRATION_PHONE',
    'phoneNumber--phoneDeviceType': 'PHONE_DEVICE_TYPE',
    'phoneNumber--countryPhoneCode': 'COUNTRY',
    'country': 'COUNTRY',
    'source--source': 'JOB_BOARD',
    'candidateIsPreviousWorker': 'PREVIOUS_WORKER',
    'address--addressLine1': 'ADDRESS',
    'address--city': 'CITY',
    'address--countryRegion': 'STATE',
    'address--postalCode': 'POSTAL_CODE',
    'phoneNumber--phoneType':'PHONE_DEVICE_TYPE',

    # Self Identity fields
    'selfIdentifiedDisabilityData--name': 'LEGAL_NAME',
    'selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input': 'TODAY_MONTH',
    'selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input': 'TODAY_DAY',
    'selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input': 'TODAY_YEAR',
    
    # Professional fields
    'currentCompany': 'CURRENT_COMPANY',
    'currentRole': 'CURRENT_ROLE',
    'github': 'GITHUB_URL',
    'workAuthorization': 'WORK_AUTHORIZATION',
    'visaStatus': 'VISA_STATUS',
    'requiresSponsorship': 'SPONSORSHIP_REQUIRED',
    "resumeAttachments--attachments": 'RESUME_PATH',
    'select-files': 'RESUME_PATH',
    'file-upload-input-ref': 'RESUME_PATH',

    # Personal info with button dropdown support
    'personalInfoPerson--gender': 'GENDER', 
    'personalInfoUS--gender':'GENDER',
    'personalInfoUS--ethnicity': 'ETHNICITY',
    'personalInfoUS--veteranStatus': 'VETERAN_STATUS',
    'personalInfoUS--disability': 'DISABILITY_STATUS',
    
    # Terms and Conditions checkbox
    'termsAndConditions--acceptTermsAndAgreements': 'ACCEPT_TERMS',

    # Application questions (using labels as keys)
    'Do you certify you meet all minimum qualifications for this job as outlined in the job posting?': 'QUALIFICATIONS_MET',
    'Would you like to receive mobile text message updates relating to your employment relationship with Walmart?': 'WALMART_MESSAGES',
    "Do you have the unrestricted right to work in the country to which you're applying?": 'WORK_ELIGIBILITY',
    'Please select your age category:': 'AGE_CATEGORY',
    'Please select your Walmart Associate Status/Affiliation:': 'WALMART_AFFILIATION',
    'Will you now or in the future require "sponsorship for an immigration-related employment benefit"?': 'REQUIRE_SPONSORSHIP',
    'Do you have Active Duty or Guard/Reserve experience in the Uniformed Services of the United States?': 'ACTIVE_DUTY_STATUS',
    "Do you have a direct family member who currently works for Walmart or Sam's Club?": 'FAMILY_MEMBER_WORKS_AT_WALMART',
    'Does the Legal Name you provided on the “My Information” page match the name on your legal ID?': 'NAME_LEGAL',
    "As a U.S. company that exports software and technology internationally, we must comply with U.S. export control laws in every country where we operate.": 'CITIZEN_OF_RESTRICTED_NATIONS',
    "Will you now or could you in the future require sponsorship to obtain work authorization or to transfer or extend your current visa?": 'REQUIRE_SPONSORSHIP',
    "Regarding future positions at Salesforce, please select one of the following options": 'FUTURE_POSITIONS',
}

# Dropdown mappings help translate environment variable values into specific
# options found in dropdown menus.
DROPDOWN_MAPPINGS = {
    'gender': {
        'Female': ['female', 'woman'],
        'Male': ['male', 'man'],
        'I don\'t wish to answer': ['na', 'n/a', 'no answer', 'decline']
    },
    'ethnicity': {
        'Asian': ['asian'],
        'White': ['white', 'caucasian'],
        'Hispanic or Latino': ['hispanic', 'latino'],
        'Black or African American': ['black', 'african american'],
        'I don\'t wish to answer': ['na', 'n/a', 'no answer', 'decline']
    },
    'veteranStatus': {
        'I am not a veteran': ['no', 'not a veteran', 'none'],
        'I identify as one or more of the classifications of protected veterans': ['yes', 'veteran']
    },
    'disability': {
        'No, I don\'t have a disability': ['no', 'none'],
        'Yes, I have a disability': ['yes'],
        'I don\'t wish to answer': ['na', 'n/a', 'no answer', 'decline']
    },
    'workAuthorization': {
        'Yes': ['yes', 'true', '1'],
        'No': ['no', 'false', '0']
    },
    'sponsorship': {
        'No': ['no', 'false', '0'],
        'Yes': ['yes', 'true', '1']
    }
}

@dataclass
class MappedField:
    """Represents a form field that has been mapped to data and is ready for filling."""
    field_id: str
    field_type: str
    value_to_fill: Any
    page_url: str
    label: str

class DataMapper:
    """
    Maps extracted form elements to user data from environment variables.
    """

    def map_data_to_form_elements(self, form_elements: List[Dict]) -> List[MappedField]:
        """
        Takes extracted form elements and maps them to environment variable data.
        It groups radio buttons by their 'name' attribute to treat them as a single field.
        """
        mapped_fields = []
        processed_radio_groups = set()

        for element in form_elements:
            is_radio = element.get('type_of_input') == 'radio'
            
            if is_radio:
                # For radio buttons, we group them by name. The field_id for mapping is the name.
                field_id = element.get('name')
                if not field_id:
                    print(f"  ⚠️ Warning: Radio button with label '{element.get('label')}' has no 'name' attribute. Skipping.")
                    continue
                
                if field_id in processed_radio_groups:
                    continue # Already processed this group
                
                processed_radio_groups.add(field_id)
            else:
                # For other fields, the id is the primary identifier.
                field_id = element.get('id_of_input_component')
                if not field_id:
                    print(f"  ⚠️ Warning: Form element with label '{element.get('label')}' has no 'id_of_input_component'. Skipping.")
                    continue

            env_var = self._find_env_variable_for_field(field_id, element.get('label', ''))
            if not env_var:
                continue

            env_value = os.getenv(env_var)
            if env_value is None:
                print(f"  ℹ️ Info: Environment variable '{env_var}' not set for field '{element.get('label', '')}'.")
                continue

            value_to_fill = self._resolve_field_value(element, env_value)

            mapped_fields.append(MappedField(
                field_id=field_id, # For radio, this is the 'name', for others it's the 'id'
                field_type=element['type_of_input'],
                value_to_fill=value_to_fill,
                page_url=element['page_url'],
                label=element.get('label', field_id) # Use field_id as fallback for label
            ))
        
        print(f"✅ Successfully mapped {len(mapped_fields)} fields to data.")
        return mapped_fields

    def _find_env_variable_for_field(self, field_id: str, field_label: str) -> Optional[str]:
        """
        Finds the corresponding environment variable for a given form field using
        exact and fuzzy matching.
        """
        field_id_lower = field_id.lower()
        field_label_lower = field_label.lower()

        # Check for exact matches in our mapping
        for key, env_var in FIELD_MAPPINGS.items():
            if key.lower() in field_id_lower or key.lower() in field_label_lower:
                return env_var

        # A simple fuzzy match: check if any part of the label/id contains a keyword
        for keyword, env_var in FIELD_MAPPINGS.items():
            # Split multi-word keywords for better matching (e.g., "firstName")
            sub_keywords = re.findall('[A-Z][^A-Z]*', keyword) or [keyword]
            for sub_key in sub_keywords:
                if sub_key.lower() in field_id_lower or sub_key.lower() in field_label_lower:
                    return env_var
        
        return None

    def _resolve_field_value(self, element: Dict, env_value: str) -> Any:
        """
        Determines the final value to be filled in a form field, handling different
        input types like dropdowns, radios, and text formatting.
        """
        field_type = element['type_of_input']

        if field_type in ['select', 'dropdown', 'radio']:
            return self._match_dropdown_option(element, env_value)
        
        if field_type == 'checkbox':
            return env_value.lower() in ['true', 'yes', '1']

        # For text fields, you could add formatting logic here if needed
        # e.g., formatting phone numbers, dates, etc.
        return env_value

    def _match_dropdown_option(self, element: Dict, env_value: str) -> str:
        """
        Matches an environment variable value to an available option in a dropdown/select field.
        """
        available_options = element['options']
        if not available_options:
            return env_value # Cannot map if no options are known

        # 1. Try for an exact, case-insensitive match
        for option in available_options:
            if option.lower() == env_value.lower():
                return option

        # 2. Use DROPDOWN_MAPPINGS for fuzzy matching
        element_id_lower = element['id_of_input_component'].lower()
        for map_key, mappings in DROPDOWN_MAPPINGS.items():
            if map_key in element_id_lower:
                for standard_value, variations in mappings.items():
                    if env_value.lower() in variations:
                        # Now find the corresponding option in the available list
                        for option in available_options:
                            if standard_value.lower() in option.lower():
                                return option

        # 3. Fallback: if no match, return the first available option as a default
        print(f"  ⚠️ Warning: No match for '{env_value}' in field '{element['label']}'. Defaulting to first option.")
        return available_options[0]
