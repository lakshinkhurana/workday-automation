#!/usr/bin/env python3
"""
Workday Page Automation - Main Orchestrator
Author: Web Automation Engineer
Date: 2025-01-26
Description: 
Main orchestrator for page-by-page Workday application automation with progress tracking.
"""

import os
import json
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

# Import existing modules
from resume_fill import WorkdayFormScraper
from direct_form_filler import DirectFormFiller

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('workday_automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class PageConfig:
    """Configuration for a specific page in the automation flow"""
    page_name: str
    page_type: str
    url_pattern: str
    form_elements: List[Dict] = field(default_factory=list)  # Using Dict to match JSON structure
    navigation_selectors: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)

@dataclass
class AutomationState:
    """Current state of the automation process"""
    current_page_index: int = 0
    total_pages: int = 0
    pages_completed: List[str] = field(default_factory=list)
    pages_failed: List[str] = field(default_factory=list)
    account_created: bool = False
    automation_start_time: float = field(default_factory=time.time)
    last_error: Optional[str] = None

@dataclass
class ProgressInfo:
    """Information about automation progress"""
    current_page: str = ""
    page_number: int = 0
    total_pages: int = 0
    percentage_complete: float = 0.0
    estimated_time_remaining: Optional[float] = None
    status: str = "initialized"  # "processing", "completed", "failed"

class ErrorHandler:
    """Handles errors and implements recovery strategies"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ErrorHandler")
    
    async def handle_account_creation_error(self, error: Exception) -> bool:
        """Handle account creation errors with appropriate recovery"""
        self.logger.error(f"Account creation error: {str(error)}")
        # Implementation will be added in later tasks
        return False
    
    async def handle_page_navigation_error(self, error: Exception) -> bool:
        """Handle page navigation errors with retry logic"""
        self.logger.error(f"Page navigation error: {str(error)}")
        # Implementation will be added in later tasks
        return False
    
    async def handle_form_filling_error(self, error: Exception) -> bool:
        """Handle form filling errors with fallback strategies"""
        self.logger.error(f"Form filling error: {str(error)}")
        # Implementation will be added in later tasks
        return False
    
    async def retry_with_backoff(self, operation: Callable, max_retries: int = 3) -> bool:
        """Retry operation with exponential backoff"""
        for attempt in range(max_retries):
            try:
                await operation()
                return True
            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff
                self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time}s...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"All {max_retries} attempts failed")
                    return False
        return False

class ProgressTracker:
    """Tracks and displays automation progress with visual progress bar"""
    
    def __init__(self):
        self.current_page = 0
        self.total_pages = 0
        self.page_names = []
        self.start_time = None
        self.page_start_times = []
        self.completed_pages = []
        self.current_page_status = "initialized"
        self.logger = logging.getLogger(f"{__name__}.ProgressTracker")
    
    def initialize(self, pages: List[str]):
        """Initialize progress tracker with list of pages"""
        self.page_names = pages.copy()
        self.total_pages = len(pages)
        self.current_page = 0
        self.start_time = time.time()
        self.page_start_times = []
        self.completed_pages = []
        self.current_page_status = "initialized"
        
        self.logger.info(f"Progress tracker initialized with {self.total_pages} pages: {', '.join(pages)}")
        self.display_progress()
    
    def update_progress(self, page_index: int, page_name: str = None):
        """Update current progress to specified page"""
        if page_index < 0 or page_index >= self.total_pages:
            self.logger.warning(f"Invalid page index: {page_index}. Must be between 0 and {self.total_pages - 1}")
            return
        
        # Mark previous pages as completed if moving forward
        if page_index > self.current_page:
            for i in range(self.current_page, page_index):
                if i not in self.completed_pages:
                    self.completed_pages.append(i)
        
        self.current_page = page_index
        
        # Update page name if provided
        if page_name and page_index < len(self.page_names):
            self.page_names[page_index] = page_name
        
        # Record page start time
        if len(self.page_start_times) <= page_index:
            self.page_start_times.extend([None] * (page_index + 1 - len(self.page_start_times)))
        
        if self.page_start_times[page_index] is None:
            self.page_start_times[page_index] = time.time()
        
        self.current_page_status = "processing"
        self.display_progress()
    
    def mark_page_completed(self, page_index: int = None):
        """Mark a specific page as completed"""
        if page_index is None:
            page_index = self.current_page
        
        if page_index not in self.completed_pages:
            self.completed_pages.append(page_index)
        
        self.current_page_status = "completed"
        self.logger.info(f"Page {page_index + 1} completed: {self.get_current_page_name()}")
        self.display_progress()
    
    def mark_page_failed(self, page_index: int = None, error_msg: str = None):
        """Mark a specific page as failed"""
        if page_index is None:
            page_index = self.current_page
        
        self.current_page_status = "failed"
        error_info = f" - {error_msg}" if error_msg else ""
        self.logger.error(f"Page {page_index + 1} failed: {self.get_current_page_name()}{error_info}")
        self.display_progress()
    
    def display_progress(self):
        """Display current progress with enhanced visual progress bar"""
        if self.total_pages == 0:
            print("No pages to process")
            return
        
        percentage = self.get_progress_percentage()
        current_page_name = self.get_current_page_name()
        
        # Create enhanced progress bar with different characters for different states
        bar_length = 40
        filled_length = int(bar_length * len(self.completed_pages) / self.total_pages)
        current_pos = int(bar_length * self.current_page / self.total_pages)
        
        # Build progress bar with different indicators
        bar = ""
        for i in range(bar_length):
            if i < filled_length:
                bar += "█"  # Completed sections
            elif i == current_pos and self.current_page_status == "processing":
                bar += "▶"  # Current processing position
            elif i == current_pos and self.current_page_status == "failed":
                bar += "✗"  # Failed position
            else:
                bar += "░"  # Remaining sections
        
        # Status indicator
        status_indicator = {
            "initialized": "🔄",
            "processing": "⚡",
            "completed": "✅",
            "failed": "❌"
        }.get(self.current_page_status, "🔄")
        
        # Time estimation
        time_info = self._get_time_info()
        
        # Create multi-line progress display
        progress_lines = [
            f"\n{'='*60}",
            f"WORKDAY AUTOMATION PROGRESS {status_indicator}",
            f"{'='*60}",
            f"Progress: [{bar}] {percentage:.1f}%",
            f"Current:  Page {self.current_page + 1}/{self.total_pages} - {current_page_name}",
            f"Status:   {self.current_page_status.title()}",
            f"Completed: {len(self.completed_pages)}/{self.total_pages} pages",
            f"Time:     {time_info}",
            f"{'='*60}\n"
        ]
        
        progress_display = "\n".join(progress_lines)
        print(progress_display)
        
        # Log concise version
        log_msg = f"Progress: {percentage:.1f}% - Page {self.current_page + 1}/{self.total_pages}: {current_page_name} ({self.current_page_status})"
        self.logger.info(log_msg)
    
    def get_progress_percentage(self) -> float:
        """Calculate progress percentage based on completed pages"""
        if self.total_pages == 0:
            return 0.0
        return (len(self.completed_pages) / self.total_pages) * 100
    
    def get_current_page_name(self) -> str:
        """Get the name of the current page"""
        if self.current_page < len(self.page_names):
            return self.page_names[self.current_page]
        return f"Page {self.current_page + 1}"
    
    def get_current_page_status(self) -> str:
        """Get the current page processing status"""
        return self.current_page_status
    
    def get_completed_pages_count(self) -> int:
        """Get the number of completed pages"""
        return len(self.completed_pages)
    
    def get_remaining_pages_count(self) -> int:
        """Get the number of remaining pages"""
        return self.total_pages - len(self.completed_pages)
    
    def is_completed(self) -> bool:
        """Check if all pages are completed"""
        return len(self.completed_pages) == self.total_pages
    
    def get_progress_info(self) -> ProgressInfo:
        """Get detailed progress information"""
        return ProgressInfo(
            current_page=self.get_current_page_name(),
            page_number=self.current_page + 1,
            total_pages=self.total_pages,
            percentage_complete=self.get_progress_percentage(),
            estimated_time_remaining=self._estimate_remaining_time(),
            status=self.current_page_status
        )
    
    def _get_time_info(self) -> str:
        """Get formatted time information"""
        if not self.start_time:
            return "Not started"
        
        elapsed = time.time() - self.start_time
        elapsed_str = self._format_duration(elapsed)
        
        estimated_remaining = self._estimate_remaining_time()
        if estimated_remaining:
            remaining_str = self._format_duration(estimated_remaining)
            return f"Elapsed: {elapsed_str}, Est. remaining: {remaining_str}"
        else:
            return f"Elapsed: {elapsed_str}"
    
    def _estimate_remaining_time(self) -> Optional[float]:
        """Estimate remaining time based on completed pages"""
        if not self.start_time or len(self.completed_pages) == 0:
            return None
        
        elapsed = time.time() - self.start_time
        avg_time_per_page = elapsed / len(self.completed_pages)
        remaining_pages = self.get_remaining_pages_count()
        
        return avg_time_per_page * remaining_pages
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def reset(self):
        """Reset the progress tracker"""
        self.current_page = 0
        self.completed_pages = []
        self.page_start_times = []
        self.start_time = time.time()
        self.current_page_status = "initialized"
        self.logger.info("Progress tracker reset")

class PageProcessor:
    """Processes individual pages in the automation flow"""
    
    def __init__(self, form_filler: DirectFormFiller):
        self.form_filler = form_filler
        self.processed_pages = set()
        self.logger = logging.getLogger(f"{__name__}.PageProcessor")
    
    async def process_page(self, page: Page, page_config: Dict) -> bool:
        """Process a single page"""
        self.logger.info(f"Processing page: {page_config.get('name', 'Unknown')}")
        # Implementation will be added in later tasks
        return True
    
    async def extract_page_json(self, page: Page) -> Dict:
        """Extract JSON configuration from current page"""
        self.logger.info("Extracting page JSON configuration")
        # Implementation will be added in later tasks
        return {}
    
    async def fill_page_forms(self, page: Page, json_data: Dict) -> bool:
        """Fill forms on current page using JSON data"""
        self.logger.info("Filling page forms")
        # Implementation will be added in later tasks
        return True
    
    async def navigate_to_next_page(self, page: Page) -> bool:
        """Navigate to the next page"""
        self.logger.info("Navigating to next page")
        # Implementation will be added in later tasks
        return True

class JSONExtractor:
    """Enhanced JSON extractor for page-specific configurations"""
    
    def __init__(self):
        self.form_mappings = {}
        self.page_configs = {}
        self.logger = logging.getLogger(f"{__name__}.JSONExtractor")
    
    def load_json_config(self, file_path: str) -> Dict:
        """Load JSON configuration from file"""
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            self.logger.info(f"Loaded JSON config from {file_path}")
            return config
        except Exception as e:
            self.logger.error(f"Failed to load JSON config from {file_path}: {str(e)}")
            return {}
    
    def extract_page_config(self, page_data: Dict) -> Dict:
        """Extract page configuration from page data"""
        # Implementation will be added in later tasks
        return {}
    
    def get_field_mappings(self, page_type: str) -> Dict:
        """Get field mappings for specific page type"""
        return self.form_mappings.get(page_type, {})
    
    def validate_json_structure(self, json_data: Dict) -> bool:
        """Validate JSON structure matches the exact format specification"""
        required_fields = ["label", "id_of_input_component", "required", "type_of_input", "options", "user_data_select_values"]
        
        # Check all required fields are present
        if not all(field in json_data for field in required_fields):
            missing_fields = [field for field in required_fields if field not in json_data]
            self.logger.warning(f"JSON validation failed - missing fields: {missing_fields}")
            return False
        
        # Validate field types
        try:
            # label should be string
            if not isinstance(json_data["label"], str):
                self.logger.warning("JSON validation failed - 'label' must be string")
                return False
            
            # id_of_input_component should be string
            if not isinstance(json_data["id_of_input_component"], str):
                self.logger.warning("JSON validation failed - 'id_of_input_component' must be string")
                return False
            
            # required should be boolean
            if not isinstance(json_data["required"], bool):
                self.logger.warning("JSON validation failed - 'required' must be boolean")
                return False
            
            # type_of_input should be one of the allowed values
            allowed_types = ["text", "textarea", "select", "multiselect", "checkbox", "radio", "date", "file", "dropdown"]
            if json_data["type_of_input"] not in allowed_types:
                self.logger.warning(f"JSON validation failed - 'type_of_input' must be one of: {allowed_types}")
                return False
            
            # options should be list
            if not isinstance(json_data["options"], list):
                self.logger.warning("JSON validation failed - 'options' must be list")
                return False
            
            # user_data_select_values should be list
            if not isinstance(json_data["user_data_select_values"], list):
                self.logger.warning("JSON validation failed - 'user_data_select_values' must be list")
                return False
            
            self.logger.debug("JSON structure validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"JSON validation error: {str(e)}")
            return False
    
    async def extract_form_element_json(self, page: Page, element) -> Dict:
        """Extract JSON for a single form element using the exact specified structure"""
        try:
            # Extract label from parent div
            label = await self.extract_label_from_parent_div(element)
            
            # Get element ID (try id, name, data-automation-id in order)
            element_id = await element.get_attribute('id') or \
                        await element.get_attribute('name') or \
                        await element.get_attribute('data-automation-id') or ""
            
            # Determine if field is required
            required = await self._is_field_required(element)
            
            # Determine input type
            input_type = await self.determine_input_type(element)
            
            # Extract options for select/radio/checkbox elements
            options = await self.extract_options_for_select_elements(element)
            
            # Generate example user data select values for choice-based inputs
            user_data_select_values = self._generate_example_values(input_type, options)
            
            # Create JSON structure matching exact specification
            form_element_json = {
                "label": label,
                "id_of_input_component": element_id,
                "required": required,
                "type_of_input": input_type,
                "options": options,
                "user_data_select_values": user_data_select_values
            }
            
            # Validate the structure before returning
            if self.validate_json_structure(form_element_json):
                self.logger.debug(f"Successfully extracted form element JSON: {element_id}")
                return form_element_json
            else:
                self.logger.warning(f"Generated JSON failed validation for element: {element_id}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error extracting form element JSON: {str(e)}")
            return {}
    
    async def extract_label_from_parent_div(self, element) -> str:
        """Extract text content from parent div elements following hierarchy strategy"""
        try:
            # Strategy 1: Look for parent div containing the input element
            parent_div = await element.query_selector('xpath=ancestor::div[1]')
            if parent_div:
                # Extract all text content from the parent div
                parent_text = await parent_div.inner_text()
                if parent_text and parent_text.strip():
                    # Clean and normalize the extracted text
                    cleaned_text = self._clean_label_text(parent_text.strip())
                    if cleaned_text:
                        self.logger.debug(f"Extracted label from immediate parent div: '{cleaned_text}'")
                        return cleaned_text
            
            # Strategy 2: Look for label element associated with input
            element_id = await element.get_attribute('id')
            if element_id:
                try:
                    frame = await element.owner_frame()
                    page = frame.page
                    label_element = await page.query_selector(f'label[for="{element_id}"]')
                    if label_element:
                        label_text = await label_element.inner_text()
                        if label_text and label_text.strip():
                            cleaned_text = self._clean_label_text(label_text.strip())
                            self.logger.debug(f"Extracted label from associated label element: '{cleaned_text}'")
                            return cleaned_text
                except:
                    pass  # Continue to next strategy
            
            # Strategy 3: Look for aria-label attribute
            aria_label = await element.get_attribute('aria-label')
            if aria_label and aria_label.strip():
                cleaned_text = self._clean_label_text(aria_label.strip())
                self.logger.debug(f"Extracted label from aria-label: '{cleaned_text}'")
                return cleaned_text
            
            # Strategy 4: Look for placeholder text as fallback
            placeholder = await element.get_attribute('placeholder')
            if placeholder and placeholder.strip():
                cleaned_text = self._clean_label_text(placeholder.strip())
                self.logger.debug(f"Extracted label from placeholder: '{cleaned_text}'")
                return cleaned_text
            
            # Strategy 5: Look for nearby text in ancestor divs (up to 3 levels)
            for level in range(2, 5):  # Check 2nd, 3rd, 4th parent
                try:
                    ancestor_div = await element.query_selector(f'xpath=ancestor::div[{level}]')
                    if ancestor_div:
                        ancestor_text = await ancestor_div.inner_text()
                        if ancestor_text and ancestor_text.strip():
                            # Look for question-like text patterns
                            lines = ancestor_text.strip().split('\n')
                            for line in lines:
                                line = line.strip()
                                if line and (line.endswith('?') or line.endswith(':') or len(line.split()) > 2):
                                    cleaned_text = self._clean_label_text(line)
                                    if cleaned_text:
                                        self.logger.debug(f"Extracted label from ancestor div level {level}: '{cleaned_text}'")
                                        return cleaned_text
                except:
                    continue
            
            # Strategy 6: Use element name/id as fallback
            element_name = await element.get_attribute('name') or await element.get_attribute('id') or ""
            if element_name:
                # Convert camelCase or snake_case to readable text
                readable_name = self._convert_name_to_label(element_name)
                self.logger.debug(f"Generated label from element name: '{readable_name}'")
                return readable_name
            
            self.logger.warning("Could not extract label from any source")
            return "Unknown Field"
            
        except Exception as e:
            self.logger.error(f"Error extracting label from parent div: {str(e)}")
            return "Unknown Field"
    
    def _clean_label_text(self, text: str) -> str:
        """Clean and normalize extracted label text"""
        if not text:
            return ""
        
        # Remove extra whitespace and newlines
        cleaned = ' '.join(text.split())
        
        # Remove common prefixes/suffixes that aren't part of the actual question
        prefixes_to_remove = ['*', '•', '-', '>', '»']
        suffixes_to_remove = ['*', '(required)', '(optional)', '(Required)', '(Optional)']
        
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
        
        # Handle special cases where text contains multiple sentences
        # Take the first sentence that looks like a question or field label
        sentences = cleaned.split('.')
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and (sentence.endswith('?') or len(sentence.split()) >= 3):
                return sentence
        
        return cleaned
    
    def _convert_name_to_label(self, name: str) -> str:
        """Convert element name/id to readable label"""
        if not name:
            return ""
        
        # Handle common patterns
        name = name.replace('--', ' ').replace('_', ' ').replace('-', ' ')
        
        # Convert camelCase to spaced words
        import re
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        
        # Capitalize first letter of each word
        words = name.split()
        capitalized_words = [word.capitalize() for word in words if word]
        
        return ' '.join(capitalized_words)
    
    async def determine_input_type(self, element) -> str:
        """Classify inputs as text|textarea|select|multiselect|checkbox|radio|date|file|dropdown"""
        try:
            # Get element tag name and type attribute
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            element_type = await element.get_attribute('type') or ""
            element_role = await element.get_attribute('role') or ""
            element_class = await element.get_attribute('class') or ""
            
            self.logger.debug(f"Determining input type - tag: {tag_name}, type: {element_type}, role: {element_role}")
            
            # Handle different element types
            if tag_name == 'select':
                # Check if it's a multiselect
                multiple = await element.get_attribute('multiple')
                if multiple is not None:
                    return "multiselect"
                return "select"
            
            elif tag_name == 'textarea':
                return "textarea"
            
            elif tag_name == 'input':
                # Handle input elements based on type attribute
                if element_type == 'checkbox':
                    return "checkbox"
                elif element_type == 'radio':
                    return "radio"
                elif element_type in ['date', 'datetime-local', 'time']:
                    return "date"
                elif element_type == 'file':
                    return "file"
                elif element_type in ['email', 'tel', 'url', 'number', 'password']:
                    return "text"  # Treat specialized text inputs as text
                elif element_type == 'text' or element_type == '' or element_type is None:
                    # Check if it behaves like a dropdown (has role="combobox" or similar)
                    if element_role in ['combobox', 'listbox'] or 'dropdown' in element_class.lower():
                        return "dropdown"
                    return "text"
                else:
                    return "text"  # Default for unknown input types
            
            elif tag_name == 'button':
                # Check if button acts as a dropdown trigger
                aria_haspopup = await element.get_attribute('aria-haspopup')
                if aria_haspopup == 'listbox' or 'dropdown' in element_class.lower():
                    return "dropdown"
                return "text"  # Treat buttons as text for now
            
            elif tag_name == 'div':
                # Some custom dropdowns are implemented as divs
                if element_role in ['combobox', 'listbox'] or 'dropdown' in element_class.lower():
                    return "dropdown"
                # Check if div contains input elements
                input_child = await element.query_selector('input')
                if input_child:
                    return await self.determine_input_type(input_child)
                return "text"
            
            else:
                # For other elements, try to determine based on role and class
                if element_role in ['combobox', 'listbox']:
                    return "dropdown"
                elif element_role == 'checkbox':
                    return "checkbox"
                elif element_role == 'radio':
                    return "radio"
                else:
                    return "text"  # Default fallback
                    
        except Exception as e:
            self.logger.error(f"Error determining input type: {str(e)}")
            return "text"  # Safe fallback
    
    async def extract_options_for_select_elements(self, element) -> List[str]:
        """Extract visible choices for select/radio/checkbox elements"""
        try:
            input_type = await self.determine_input_type(element)
            
            if input_type == "select" or input_type == "multiselect":
                return await self._extract_select_options(element)
            elif input_type == "radio":
                return await self._extract_radio_options(element)
            elif input_type == "checkbox":
                return await self._extract_checkbox_options(element)
            elif input_type == "dropdown":
                return await self._extract_dropdown_options(element)
            else:
                # For non-choice elements, return empty list
                return []
                
        except Exception as e:
            self.logger.error(f"Error extracting options: {str(e)}")
            return []
    
    async def _extract_select_options(self, select_element) -> List[str]:
        """Extract options from select element"""
        try:
            options = []
            option_elements = await select_element.query_selector_all('option')
            
            for option in option_elements:
                option_text = await option.inner_text()
                option_value = await option.get_attribute('value')
                
                # Skip empty or placeholder options
                if option_text and option_text.strip() and option_text.strip() not in ['', 'Select...', 'Choose...', '--']:
                    options.append(option_text.strip())
            
            self.logger.debug(f"Extracted {len(options)} select options")
            return options
            
        except Exception as e:
            self.logger.error(f"Error extracting select options: {str(e)}")
            return []
    
    async def _extract_radio_options(self, radio_element) -> List[str]:
        """Extract options from radio button group"""
        try:
            options = []
            
            # Get the name attribute to find all radio buttons in the same group
            radio_name = await radio_element.get_attribute('name')
            if not radio_name:
                return []
            
            # Get page from element's context
            try:
                frame = await radio_element.owner_frame()
                page = frame.page
            except:
                self.logger.warning("Could not access page from radio element")
                return []
            
            # Find all radio buttons with the same name
            radio_group = await page.query_selector_all(f'input[type="radio"][name="{radio_name}"]')
            
            for radio in radio_group:
                # Look for associated label
                radio_id = await radio.get_attribute('id')
                label_text = ""
                
                if radio_id:
                    label_element = await page.query_selector(f'label[for="{radio_id}"]')
                    if label_element:
                        label_text = await label_element.inner_text()
                
                # If no label found, look for parent label or nearby text
                if not label_text:
                    parent = await radio.query_selector('xpath=..')
                    if parent:
                        parent_text = await parent.inner_text()
                        if parent_text:
                            label_text = parent_text.strip()
                
                # Get value attribute as fallback
                if not label_text:
                    label_text = await radio.get_attribute('value') or ""
                
                if label_text and label_text.strip():
                    options.append(label_text.strip())
            
            self.logger.debug(f"Extracted {len(options)} radio options")
            return options
            
        except Exception as e:
            self.logger.error(f"Error extracting radio options: {str(e)}")
            return []
    
    async def _extract_checkbox_options(self, checkbox_element) -> List[str]:
        """Extract options from checkbox group"""
        try:
            options = []
            
            # Get page from element's context
            try:
                frame = await checkbox_element.owner_frame()
                page = frame.page
            except:
                self.logger.warning("Could not access page from checkbox element")
                return []
            
            # For individual checkbox, just get its label
            checkbox_id = await checkbox_element.get_attribute('id')
            
            if checkbox_id:
                label_element = await page.query_selector(f'label[for="{checkbox_id}"]')
                if label_element:
                    label_text = await label_element.inner_text()
                    if label_text and label_text.strip():
                        options.append(label_text.strip())
            
            # If no label found, look for parent text
            if not options:
                parent = await checkbox_element.query_selector('xpath=..')
                if parent:
                    parent_text = await parent.inner_text()
                    if parent_text and parent_text.strip():
                        options.append(parent_text.strip())
            
            # Look for other checkboxes in the same group (same name attribute)
            checkbox_name = await checkbox_element.get_attribute('name')
            if checkbox_name:
                checkbox_group = await page.query_selector_all(f'input[type="checkbox"][name="{checkbox_name}"]')
                
                for checkbox in checkbox_group:
                    cb_id = await checkbox.get_attribute('id')
                    if cb_id and cb_id != checkbox_id:  # Don't duplicate the original
                        cb_label = await page.query_selector(f'label[for="{cb_id}"]')
                        if cb_label:
                            cb_text = await cb_label.inner_text()
                            if cb_text and cb_text.strip() and cb_text.strip() not in options:
                                options.append(cb_text.strip())
            
            self.logger.debug(f"Extracted {len(options)} checkbox options")
            return options
            
        except Exception as e:
            self.logger.error(f"Error extracting checkbox options: {str(e)}")
            return []
    
    async def _extract_dropdown_options(self, dropdown_element) -> List[str]:
        """Extract options from custom dropdown elements"""
        try:
            options = []
            
            # Get page from element's context
            try:
                frame = await dropdown_element.owner_frame()
                page = frame.page
            except:
                self.logger.warning("Could not access page from dropdown element")
                return []
            
            # Try to trigger dropdown to show options
            try:
                await dropdown_element.click()
                await asyncio.sleep(0.5)  # Wait for dropdown to open
            except:
                pass  # Continue even if click fails
            
            # Look for dropdown options in various common patterns
            option_selectors = [
                '[role="option"]',
                '.dropdown-option',
                '.dropdown-item',
                'li[data-value]',
                'div[data-value]',
                '.option',
                '.choice'
            ]
            
            for selector in option_selectors:
                try:
                    option_elements = await page.query_selector_all(selector)
                    if option_elements:
                        for option in option_elements:
                            option_text = await option.inner_text()
                            if option_text and option_text.strip() and option_text.strip() not in options:
                                options.append(option_text.strip())
                        break  # Stop after finding options with one selector
                except:
                    continue
            
            # Try to close dropdown if we opened it
            try:
                await page.keyboard.press('Escape')
            except:
                pass
            
            self.logger.debug(f"Extracted {len(options)} dropdown options")
            return options
            
        except Exception as e:
            self.logger.error(f"Error extracting dropdown options: {str(e)}")
            return []
    
    def _generate_example_values(self, input_type: str, options: List[str]) -> List[str]:
        """Generate example values for testing choice-based inputs"""
        if input_type in ["select", "multiselect", "radio", "dropdown"] and options:
            # For choice-based inputs, return the first option as example
            return [options[0]]
        elif input_type == "checkbox" and options:
            # For checkboxes, return the option text
            return [options[0]]
        else:
            # For non-choice inputs, return empty list
            return []
    
    async def _is_field_required(self, element) -> bool:
        """Determine if a form field is required"""
        try:
            # Check required attribute
            required_attr = await element.get_attribute('required')
            if required_attr is not None:
                return True
            
            # Check aria-required attribute
            aria_required = await element.get_attribute('aria-required')
            if aria_required == 'true':
                return True
            
            # Look for visual indicators in parent elements
            parent = await element.query_selector('xpath=..')
            if parent:
                parent_text = await parent.inner_text()
                if parent_text and ('*' in parent_text or 'required' in parent_text.lower()):
                    return True
            
            # Check for required class names
            element_class = await element.get_attribute('class') or ""
            if 'required' in element_class.lower():
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error determining if field is required: {str(e)}")
            return False

class WorkdayPageAutomator:
    """Main orchestrator for Workday page automation"""
    
    def __init__(self):
        self.progress_tracker = ProgressTracker()
        self.page_processor = PageProcessor(DirectFormFiller())
        self.json_extractor = JSONExtractor()
        self.form_filler = DirectFormFiller()
        self.account_creator = None  # Will be initialized when needed
        self.error_handler = ErrorHandler()
        self.automation_state = AutomationState()
        self.logger = logging.getLogger(f"{__name__}.WorkdayPageAutomator")
        
        # Load configuration
        self.config = self._load_configuration()
        
        self.logger.info("WorkdayPageAutomator initialized")
    
    def _load_configuration(self) -> Dict:
        """Load automation configuration"""
        config = {
            "max_retries": int(os.getenv("AUTOMATION_MAX_RETRIES", "3")),
            "page_timeout": int(os.getenv("AUTOMATION_PAGE_TIMEOUT", "30000")),
            "navigation_delay": int(os.getenv("AUTOMATION_NAVIGATION_DELAY", "2000")),
            "headless": os.getenv("AUTOMATION_HEADLESS", "false").lower() == "true"
        }
        self.logger.info(f"Loaded configuration: {config}")
        return config
    
    async def run_automation(self) -> bool:
        """Main automation orchestration method"""
        try:
            self.logger.info("Starting Workday page automation")
            self.automation_state.automation_start_time = time.time()
            
            # Implementation will be added in later tasks
            # This will coordinate:
            # 1. Account creation
            # 2. Page discovery
            # 3. Sequential page processing
            # 4. Progress tracking
            # 5. Error handling and recovery
            
            self.logger.info("Automation orchestration framework ready")
            return True
            
        except Exception as e:
            self.logger.error(f"Automation failed: {str(e)}")
            self.automation_state.last_error = str(e)
            return False
    
    async def create_account(self) -> bool:
        """Create account using existing resume_fill.py functionality"""
        try:
            self.logger.info("Starting account creation")
            # Implementation will be added in later tasks
            self.automation_state.account_created = True
            return True
        except Exception as e:
            self.logger.error(f"Account creation failed: {str(e)}")
            return await self.error_handler.handle_account_creation_error(e)
    
    async def process_all_pages(self) -> bool:
        """Process all pages in the automation flow"""
        try:
            self.logger.info("Starting page processing")
            # Implementation will be added in later tasks
            return True
        except Exception as e:
            self.logger.error(f"Page processing failed: {str(e)}")
            return False

# Main execution
async def main():
    """Main entry point for the automation"""
    automator = WorkdayPageAutomator()
    success = await automator.run_automation()
    
    if success:
        logger.info("Workday automation completed successfully")
    else:
        logger.error("Workday automation failed")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())