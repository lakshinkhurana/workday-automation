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
        self.processed_pages = set()  # Track processed pages to avoid duplicates
        self.page_states = {}  # Store page state information
        self.json_extractor = JSONExtractor()
        self.logger = logging.getLogger(f"{__name__}.PageProcessor")
        
        # Page type patterns for classification
        self.page_patterns = {
            "login": ["login", "sign-in", "authentication", "signin"],
            "my_information": ["my-information", "personal", "profile", "basic-information"],
            "job_application": ["job-application", "application", "apply", "position"],
            "eeo": ["eeo", "equal-employment", "diversity", "demographics"],
            "review": ["review", "summary", "confirm", "submit", "final"]
        }
    
    async def process_page(self, page: Page, page_config: Dict = None) -> bool:
        """
        Process a single page with comprehensive handling
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        """
        try:
            # Get current page URL and title for identification
            current_url = page.url
            page_title = await page.title()
            
            self.logger.info(f"Processing page: {page_title} ({current_url})")
            
            # Check if page was already processed to avoid duplicates (Requirement 3.5)
            page_id = self._generate_page_id(current_url, page_title)
            if self._is_page_already_processed(page_id):
                self.logger.info(f"Page {page_id} already processed, skipping")
                return True
            
            # Detect and classify the page type (Requirement 3.1)
            page_type = await self.detect_page_type(page)
            self.logger.info(f"Detected page type: {page_type}")
            
            # Update page state tracking
            self._update_page_state(page_id, {
                "url": current_url,
                "title": page_title,
                "type": page_type,
                "status": "processing",
                "timestamp": time.time()
            })
            
            # Extract page configuration and form data (Requirement 3.2)
            page_json = await self.extract_page_json(page)
            if not page_json:
                self.logger.warning("No JSON configuration extracted from page")
            
            # Fill forms on the current page (Requirement 3.3)
            form_fill_success = await self.fill_page_forms(page, page_json)
            if not form_fill_success:
                self.logger.error("Form filling failed")
                self._update_page_state(page_id, {"status": "failed", "error": "Form filling failed"})
                return False
            
            # Navigate to next page (Requirement 3.4)
            navigation_success = await self.navigate_to_next_page(page)
            if not navigation_success:
                self.logger.error("Navigation to next page failed")
                self._update_page_state(page_id, {"status": "failed", "error": "Navigation failed"})
                return False
            
            # Mark page as successfully processed
            self._mark_page_processed(page_id)
            self._update_page_state(page_id, {"status": "completed"})
            
            self.logger.info(f"Successfully processed page: {page_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing page: {str(e)}")
            if 'page_id' in locals():
                self._update_page_state(page_id, {"status": "failed", "error": str(e)})
            return False
    
    async def detect_page_type(self, page: Page) -> str:
        """
        Detect and classify the current page type
        Requirement: 3.1 - Add page detection and classification logic
        """
        try:
            current_url = page.url.lower()
            page_title = (await page.title()).lower()
            
            # Get page content for additional analysis
            try:
                page_content = await page.content()
                page_content_lower = page_content.lower()
            except:
                page_content_lower = ""
            
            self.logger.debug(f"Analyzing page - URL: {current_url}, Title: {page_title}")
            
            # Check URL patterns first (most reliable)
            for page_type, patterns in self.page_patterns.items():
                for pattern in patterns:
                    if pattern in current_url:
                        self.logger.debug(f"Page type '{page_type}' detected from URL pattern: {pattern}")
                        return page_type
            
            # Check page title patterns
            for page_type, patterns in self.page_patterns.items():
                for pattern in patterns:
                    if pattern in page_title:
                        self.logger.debug(f"Page type '{page_type}' detected from title pattern: {pattern}")
                        return page_type
            
            # Check page content for specific indicators
            content_indicators = {
                "login": ["password", "email", "username", "sign in", "log in"],
                "my_information": ["first name", "last name", "phone", "address", "personal information"],
                "job_application": ["position", "job title", "resume", "cover letter", "application"],
                "eeo": ["ethnicity", "gender", "disability", "veteran", "equal employment"],
                "review": ["review", "submit", "confirm", "summary", "application summary"]
            }
            
            for page_type, indicators in content_indicators.items():
                indicator_count = sum(1 for indicator in indicators if indicator in page_content_lower)
                if indicator_count >= 2:  # Require at least 2 indicators for content-based detection
                    self.logger.debug(f"Page type '{page_type}' detected from content indicators")
                    return page_type
            
            # Check for specific form elements that indicate page type
            form_indicators = await self._analyze_form_elements_for_page_type(page)
            if form_indicators:
                self.logger.debug(f"Page type '{form_indicators}' detected from form analysis")
                return form_indicators
            
            # Default fallback
            self.logger.warning("Could not determine specific page type, using 'unknown'")
            return "unknown"
            
        except Exception as e:
            self.logger.error(f"Error detecting page type: {str(e)}")
            return "unknown"
    
    async def _analyze_form_elements_for_page_type(self, page: Page) -> str:
        """Analyze form elements to help determine page type"""
        try:
            # Look for specific input patterns that indicate page type
            input_elements = await page.query_selector_all('input, select, textarea')
            
            field_indicators = {
                "login": ["password", "email", "username"],
                "my_information": ["firstname", "lastname", "phone", "address"],
                "job_application": ["resume", "coverletter", "position"],
                "eeo": ["ethnicity", "gender", "disability", "veteran"],
                "review": []  # Review pages typically have fewer inputs
            }
            
            found_fields = []
            for element in input_elements[:10]:  # Limit to first 10 elements for performance
                try:
                    element_name = await element.get_attribute('name') or ""
                    element_id = await element.get_attribute('id') or ""
                    element_placeholder = await element.get_attribute('placeholder') or ""
                    
                    field_text = f"{element_name} {element_id} {element_placeholder}".lower()
                    found_fields.append(field_text)
                except:
                    continue
            
            # Score each page type based on field matches
            type_scores = {}
            for page_type, indicators in field_indicators.items():
                score = 0
                for indicator in indicators:
                    for field in found_fields:
                        if indicator in field:
                            score += 1
                type_scores[page_type] = score
            
            # Return the page type with the highest score (if > 0)
            if type_scores:
                best_type = max(type_scores, key=type_scores.get)
                if type_scores[best_type] > 0:
                    return best_type
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error analyzing form elements: {str(e)}")
            return ""
    
    async def extract_page_json(self, page: Page) -> Dict:
        """
        Extract JSON configuration from current page
        Requirement: 3.2 - Create base methods for form extraction
        """
        try:
            self.logger.info("Extracting JSON configuration from current page")
            
            # Find all form elements on the page
            form_elements = await page.query_selector_all('input, select, textarea, button[role="button"]')
            
            extracted_elements = []
            
            for element in form_elements:
                try:
                    # Skip hidden or disabled elements
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if not is_visible or not is_enabled:
                        continue
                    
                    # Extract JSON for this element using JSONExtractor
                    element_json = await self.json_extractor.extract_form_element_json(page, element)
                    
                    if element_json and element_json.get('id_of_input_component'):
                        extracted_elements.append(element_json)
                        self.logger.debug(f"Extracted element: {element_json.get('label', 'Unknown')}")
                
                except Exception as e:
                    self.logger.warning(f"Error extracting element JSON: {str(e)}")
                    continue
            
            # Create page configuration structure
            page_config = {
                "page_url": page.url,
                "page_title": await page.title(),
                "extraction_timestamp": time.time(),
                "form_elements": extracted_elements,
                "total_elements": len(extracted_elements)
            }
            
            self.logger.info(f"Extracted {len(extracted_elements)} form elements from page")
            return page_config
            
        except Exception as e:
            self.logger.error(f"Error extracting page JSON: {str(e)}")
            return {}
    
    async def fill_page_forms(self, page: Page, json_data: Dict) -> bool:
        """
        Fill forms on current page using JSON data
        Requirement: 3.3 - Create base methods for form extraction and navigation
        """
        try:
            if not json_data or not json_data.get('form_elements'):
                self.logger.warning("No form elements found in JSON data")
                return True  # Not necessarily an error if no forms to fill
            
            form_elements = json_data['form_elements']
            self.logger.info(f"Attempting to fill {len(form_elements)} form elements")
            
            filled_count = 0
            failed_count = 0
            
            for element_data in form_elements:
                try:
                    element_id = element_data.get('id_of_input_component')
                    element_label = element_data.get('label', 'Unknown')
                    element_type = element_data.get('type_of_input', 'text')
                    is_required = element_data.get('required', False)
                    
                    if not element_id:
                        self.logger.warning(f"No ID found for element: {element_label}")
                        continue
                    
                    # Find the element on the page
                    element = await self._find_element_by_id(page, element_id)
                    if not element:
                        self.logger.warning(f"Could not find element with ID: {element_id}")
                        if is_required:
                            failed_count += 1
                        continue
                    
                    # Fill the element based on its type
                    fill_success = await self._fill_form_element(page, element, element_data)
                    
                    if fill_success:
                        filled_count += 1
                        self.logger.debug(f"Successfully filled: {element_label}")
                    else:
                        failed_count += 1
                        self.logger.warning(f"Failed to fill: {element_label}")
                        if is_required:
                            self.logger.error(f"Required field failed: {element_label}")
                
                except Exception as e:
                    failed_count += 1
                    self.logger.error(f"Error filling element {element_data.get('label', 'Unknown')}: {str(e)}")
            
            self.logger.info(f"Form filling completed - Filled: {filled_count}, Failed: {failed_count}")
            
            # Consider success if we filled at least some elements and no required fields failed
            return filled_count > 0 or len(form_elements) == 0
            
        except Exception as e:
            self.logger.error(f"Error filling page forms: {str(e)}")
            return False
    
    async def _find_element_by_id(self, page: Page, element_id: str):
        """Find element by ID, name, or data-automation-id"""
        try:
            # Try different selector strategies
            selectors = [
                f'#{element_id}',  # ID selector
                f'[name="{element_id}"]',  # Name attribute
                f'[data-automation-id="{element_id}"]',  # Data automation ID
                f'[id="{element_id}"]'  # Explicit ID attribute
            ]
            
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return element
                except:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding element by ID {element_id}: {str(e)}")
            return None
    
    async def _fill_form_element(self, page: Page, element, element_data: Dict) -> bool:
        """Fill a single form element based on its type and data"""
        try:
            element_type = element_data.get('type_of_input', 'text')
            user_values = element_data.get('user_data_select_values', [])
            options = element_data.get('options', [])
            
            # Get a value to fill
            fill_value = self._get_fill_value(element_type, user_values, options, element_data)
            
            if not fill_value:
                self.logger.debug(f"No value to fill for element type: {element_type}")
                return True  # Not an error if no value needed
            
            # Fill based on element type
            if element_type == 'text' or element_type == 'textarea':
                await element.fill(fill_value)
                
            elif element_type == 'select':
                await element.select_option(value=fill_value)
                
            elif element_type == 'checkbox':
                is_checked = await element.is_checked()
                if (fill_value.lower() in ['true', 'yes', '1']) != is_checked:
                    await element.click()
                    
            elif element_type == 'radio':
                await element.click()
                
            elif element_type == 'dropdown':
                # For custom dropdowns, try clicking and selecting
                await element.click()
                await asyncio.sleep(0.5)  # Wait for dropdown to open
                
                # Try to find and click the option
                option_selectors = [
                    f'[role="option"]:has-text("{fill_value}")',
                    f'.dropdown-option:has-text("{fill_value}")',
                    f'li:has-text("{fill_value}")'
                ]
                
                for selector in option_selectors:
                    try:
                        option_element = await page.query_selector(selector)
                        if option_element:
                            await option_element.click()
                            break
                    except:
                        continue
            
            # Add small delay after filling
            await asyncio.sleep(0.2)
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling form element: {str(e)}")
            return False
    
    def _get_fill_value(self, element_type: str, user_values: List[str], options: List[str], element_data: Dict) -> str:
        """Get appropriate value to fill based on element type and available data"""
        # Use user_data_select_values if available
        if user_values:
            return user_values[0]
        
        # Use first option for choice-based elements
        if element_type in ['select', 'radio', 'dropdown'] and options:
            return options[0]
        
        # Generate default values based on element type and label
        label = element_data.get('label', '').lower()
        
        if element_type == 'checkbox':
            return 'false'  # Default to unchecked
        
        # Generate contextual default values based on label
        if 'email' in label:
            return 'test@example.com'
        elif 'phone' in label:
            return '555-123-4567'
        elif 'name' in label:
            if 'first' in label:
                return 'John'
            elif 'last' in label:
                return 'Doe'
            else:
                return 'John Doe'
        elif 'address' in label:
            return '123 Main St'
        elif 'city' in label:
            return 'New York'
        elif 'zip' in label or 'postal' in label:
            return '10001'
        elif 'date' in label:
            return '01/01/2000'
        else:
            return 'Test Value'
    
    async def navigate_to_next_page(self, page: Page) -> bool:
        """
        Navigate to the next page in the application flow
        Requirement: 3.4 - Create base methods for navigation
        """
        try:
            self.logger.info("Attempting to navigate to next page")
            
            # Common navigation button selectors (in order of preference)
            navigation_selectors = [
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button:has-text("Submit")',
                'button:has-text("Save and Continue")',
                'input[type="submit"]',
                'button[type="submit"]',
                '.next-button',
                '.continue-button',
                '.submit-button',
                'a:has-text("Next")',
                'a:has-text("Continue")'
            ]
            
            # Try each selector until we find a clickable element
            for selector in navigation_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        
                        if is_visible and is_enabled:
                            self.logger.info(f"Found navigation element with selector: {selector}")
                            
                            # Click the navigation element
                            await element.click()
                            
                            # Wait for navigation to complete
                            await self._wait_for_navigation(page)
                            
                            self.logger.info("Successfully navigated to next page")
                            return True
                
                except Exception as e:
                    self.logger.debug(f"Navigation selector '{selector}' failed: {str(e)}")
                    continue
            
            # If no standard navigation found, try form submission
            try:
                form_element = await page.query_selector('form')
                if form_element:
                    self.logger.info("Attempting form submission for navigation")
                    await page.keyboard.press('Enter')
                    await self._wait_for_navigation(page)
                    return True
            except:
                pass
            
            self.logger.warning("No navigation method found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to next page: {str(e)}")
            return False
    
    async def _wait_for_navigation(self, page: Page, timeout: int = 10000):
        """Wait for page navigation to complete"""
        try:
            # Wait for either navigation or network idle
            await asyncio.wait_for(
                page.wait_for_load_state('networkidle'),
                timeout=timeout/1000
            )
        except asyncio.TimeoutError:
            self.logger.warning("Navigation wait timed out")
        except Exception as e:
            self.logger.debug(f"Navigation wait error: {str(e)}")
    
    def _generate_page_id(self, url: str, title: str) -> str:
        """Generate unique identifier for a page"""
        import hashlib
        page_info = f"{url}_{title}"
        return hashlib.md5(page_info.encode()).hexdigest()[:12]
    
    def _is_page_already_processed(self, page_id: str) -> bool:
        """
        Check if page was already processed to avoid duplicate processing
        Requirement: 3.5 - Implement page state tracking to avoid duplicate processing
        """
        return page_id in self.processed_pages
    
    def _mark_page_processed(self, page_id: str):
        """Mark a page as processed"""
        self.processed_pages.add(page_id)
        self.logger.debug(f"Marked page as processed: {page_id}")
    
    def _update_page_state(self, page_id: str, state_data: Dict):
        """
        Update page state information
        Requirement: 3.5 - Implement page state tracking
        """
        if page_id not in self.page_states:
            self.page_states[page_id] = {}
        
        self.page_states[page_id].update(state_data)
        self.logger.debug(f"Updated page state for {page_id}: {state_data}")
    
    def get_page_state(self, page_id: str) -> Dict:
        """Get current state of a specific page"""
        return self.page_states.get(page_id, {})
    
    def get_processed_pages(self) -> set:
        """Get set of all processed page IDs"""
        return self.processed_pages.copy()
    
    def get_all_page_states(self) -> Dict:
        """Get all page states"""
        return self.page_states.copy()
    
    def reset_page_tracking(self):
        """Reset page tracking state"""
        self.processed_pages.clear()
        self.page_states.clear()
        self.logger.info("Page tracking state reset")

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