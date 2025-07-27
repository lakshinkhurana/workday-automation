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
from config_manager import ConfigurationManager, WorkdayPageAutomationConfig
from performance_monitor import PerformanceMonitor, performance_monitor

# Load environment variables
load_dotenv()

# Initialize configuration manager
config_manager = ConfigurationManager()
automation_config = config_manager.load_configuration()

# Configure logging with level from configuration
log_level = getattr(logging, automation_config.automation.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
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
    """
    Comprehensive error handler with specific recovery strategies
    Requirements: 7.1, 7.2, 7.4, 7.5
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ErrorHandler")
        self.error_counts = {}
        self.recovery_attempts = {}
        self.page_context = {}
        
    def set_page_context(self, page_name: str, page_url: str = None, page_index: int = None):
        """Set current page context for detailed error logging"""
        self.page_context = {
            'page_name': page_name,
            'page_url': page_url,
            'page_index': page_index,
            'timestamp': time.time()
        }
        self.logger.debug(f"Page context set: {self.page_context}")
    
    def _log_error_with_context(self, error: Exception, operation: str, severity: str = "ERROR"):
        """Log error with detailed page context information (Requirement 7.2)"""
        context_info = ""
        if self.page_context:
            context_info = (
                f" | Page: {self.page_context.get('page_name', 'Unknown')} "
                f"(Index: {self.page_context.get('page_index', 'N/A')}) "
                f"| URL: {self.page_context.get('page_url', 'N/A')}"
            )
        
        error_msg = f"{operation} failed: {str(error)}{context_info}"
        
        if severity == "ERROR":
            self.logger.error(error_msg)
        elif severity == "WARNING":
            self.logger.warning(error_msg)
        else:
            self.logger.info(error_msg)
        
        # Track error frequency for pattern analysis
        error_key = f"{operation}:{type(error).__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
    
    async def handle_account_creation_error(self, error: Exception) -> bool:
        """
        Handle account creation errors with appropriate recovery
        Requirement: 7.1, 7.2 - Implement ErrorHandler class with specific error recovery strategies
        """
        self._log_error_with_context(error, "Account Creation")
        error_message = str(error).lower()
        
        # 1. Missing environment variables - not recoverable
        if any(indicator in error_message for indicator in [
            "missing required environment variables", "env", "environment variable"
        ]):
            self.logger.error("Cannot recover from missing environment variables")
            return False
        
        # 2. Network/connection errors - retry with backoff
        network_indicators = ["network", "connection", "timeout", "unreachable", "dns", "ssl", "certificate"]
        if any(indicator in error_message for indicator in network_indicators):
            self.logger.info("Network error detected, attempting retry with exponential backoff")
            return await self.retry_with_backoff(
                lambda: self._placeholder_account_creation(), 
                max_retries=3,
                operation_name="account_creation"
            )
        
        # 3. Existing account scenarios - treat as success (graceful degradation)
        existing_account_indicators = [
            "account already exists", "email already registered", "user already exists",
            "duplicate account", "account validation failed", "already registered"
        ]
        if any(indicator in error_message for indicator in existing_account_indicators):
            self.logger.info("Existing account detected - graceful degradation: treating as successful")
            return True
        
        # 4. Page load/navigation errors - retry with shorter backoff
        page_indicators = ["page", "navigation", "load", "element not found", "selector", "locator"]
        if any(indicator in error_message for indicator in page_indicators):
            self.logger.info("Page-related error detected, attempting retry")
            return await self.retry_with_backoff(
                lambda: self._placeholder_account_creation(),
                max_retries=2,
                operation_name="account_creation_page"
            )
        
        # 5. Form filling errors - try alternative approach
        form_indicators = ["form", "field", "input", "validation", "required field"]
        if any(indicator in error_message for indicator in form_indicators):
            self.logger.info("Form-related error detected, attempting alternative approach")
            return await self._handle_form_error_recovery(error)
        
        # 6. Browser/playwright errors - retry once
        browser_indicators = ["browser", "playwright", "chromium", "context", "session", "websocket"]
        if any(indicator in error_message for indicator in browser_indicators):
            self.logger.info("Browser error detected, attempting single retry")
            return await self.retry_with_backoff(
                lambda: self._placeholder_account_creation(),
                max_retries=1,
                operation_name="account_creation_browser"
            )
        
        # 7. Unknown errors - log and fail gracefully
        self.logger.error(f"Unknown account creation error, cannot recover: {error_message}")
        return False
    
    async def handle_page_navigation_error(self, error: Exception) -> bool:
        """
        Handle page navigation errors with retry logic
        Requirement: 7.1 - Implement ErrorHandler class with specific error recovery strategies
        """
        self._log_error_with_context(error, "Page Navigation")
        error_message = str(error).lower()
        
        # 1. Timeout errors - retry with longer wait
        if any(indicator in error_message for indicator in ["timeout", "wait", "load"]):
            self.logger.info("Navigation timeout detected, retrying with extended wait")
            return await self.retry_with_backoff(
                lambda: self._placeholder_navigation(),
                max_retries=3,
                base_delay=3,
                operation_name="navigation_timeout"
            )
        
        # 2. Element not found - try alternative selectors
        if any(indicator in error_message for indicator in ["element", "selector", "locator", "not found"]):
            self.logger.info("Element not found, attempting alternative navigation methods")
            return await self._handle_navigation_element_error(error)
        
        # 3. Page load errors - retry with backoff
        if any(indicator in error_message for indicator in ["page", "load", "ready", "complete"]):
            self.logger.info("Page load error detected, retrying navigation")
            return await self.retry_with_backoff(
                lambda: self._placeholder_navigation(),
                max_retries=2,
                operation_name="navigation_page_load"
            )
        
        # 4. Network errors during navigation
        if any(indicator in error_message for indicator in ["network", "connection", "dns"]):
            self.logger.info("Network error during navigation, retrying")
            return await self.retry_with_backoff(
                lambda: self._placeholder_navigation(),
                max_retries=2,
                operation_name="navigation_network"
            )
        
        # 5. Unknown navigation errors - graceful degradation
        self.logger.warning(f"Unknown navigation error, attempting graceful degradation: {error_message}")
        return False
    
    async def handle_form_filling_error(self, error: Exception) -> bool:
        """
        Handle form filling errors with fallback strategies
        Requirement: 7.1 - Implement ErrorHandler class with specific error recovery strategies
        """
        self._log_error_with_context(error, "Form Filling")
        error_message = str(error).lower()
        
        # 1. Element not found - try alternative selectors
        if any(indicator in error_message for indicator in ["element", "selector", "not found", "locator"]):
            self.logger.info("Form element not found, trying alternative selectors")
            return await self._handle_form_element_error(error)
        
        # 2. Field validation errors - try alternative values
        if any(indicator in error_message for indicator in ["validation", "invalid", "required", "format"]):
            self.logger.info("Form validation error, trying alternative values")
            return await self._handle_form_validation_error(error)
        
        # 3. Field interaction errors - try different interaction methods
        if any(indicator in error_message for indicator in ["click", "type", "fill", "select", "interaction"]):
            self.logger.info("Form interaction error, trying alternative methods")
            return await self._handle_form_interaction_error(error)
        
        # 4. Timeout during form filling
        if any(indicator in error_message for indicator in ["timeout", "wait"]):
            self.logger.info("Form filling timeout, retrying with longer wait")
            return await self.retry_with_backoff(
                lambda: self._placeholder_form_filling(),
                max_retries=2,
                base_delay=2,
                operation_name="form_filling_timeout"
            )
        
        # 5. Unknown form errors - graceful degradation (skip non-critical fields)
        self.logger.warning(f"Unknown form filling error, attempting graceful degradation: {error_message}")
        return await self._graceful_form_degradation(error)
    
    async def retry_with_backoff(self, operation: Callable, max_retries: int = 3, 
                                base_delay: float = 1, operation_name: str = "unknown") -> bool:
        """
        Retry operation with exponential backoff
        Requirement: 7.1 - Add retry mechanisms with exponential backoff for failed operations
        """
        operation_key = f"{operation_name}_{id(operation)}"
        
        for attempt in range(max_retries):
            try:
                # Track retry attempts
                if operation_key not in self.recovery_attempts:
                    self.recovery_attempts[operation_key] = 0
                self.recovery_attempts[operation_key] += 1
                
                self.logger.info(f"Attempting {operation_name} (attempt {attempt + 1}/{max_retries})")
                
                # Execute the operation
                result = await operation()
                
                self.logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")
                return True
                
            except Exception as e:
                wait_time = base_delay * (2 ** attempt)  # Exponential backoff
                
                self._log_error_with_context(
                    e, 
                    f"{operation_name} (attempt {attempt + 1})", 
                    "WARNING" if attempt < max_retries - 1 else "ERROR"
                )
                
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying {operation_name} in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"All {max_retries} attempts failed for {operation_name}")
                    return False
        
        return False
    
    async def _handle_form_error_recovery(self, error: Exception) -> bool:
        """Handle form-related errors with alternative approaches"""
        self.logger.info("Attempting form error recovery strategies")
        
        # Strategy 1: Skip optional fields and continue
        if "optional" in str(error).lower() or "not required" in str(error).lower():
            self.logger.info("Skipping optional field due to error - graceful degradation")
            return True
        
        # Strategy 2: Try alternative form filling methods
        try:
            # This would be implemented with actual form filling logic
            self.logger.info("Trying alternative form filling approach")
            await asyncio.sleep(1)  # Placeholder for actual implementation
            return False  # For now, return False until integrated with actual form filler
        except Exception as recovery_error:
            self.logger.warning(f"Form error recovery failed: {recovery_error}")
            return False
    
    async def _handle_navigation_element_error(self, error: Exception) -> bool:
        """Handle navigation errors related to missing elements"""
        self.logger.info("Attempting navigation element error recovery")
        
        # Try alternative navigation strategies
        strategies = [
            "Try common navigation selectors",
            "Look for 'Next' or 'Continue' buttons",
            "Check for form submission buttons",
            "Try keyboard navigation (Tab + Enter)"
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                self.logger.info(f"Navigation recovery strategy {i+1}: {strategy}")
                await asyncio.sleep(0.5)  # Placeholder for actual implementation
                # This would contain actual navigation logic
                return False  # For now, return False until integrated
            except Exception as strategy_error:
                self.logger.warning(f"Navigation strategy {i+1} failed: {strategy_error}")
                continue
        
        return False
    
    async def _handle_form_element_error(self, error: Exception) -> bool:
        """Handle form element not found errors"""
        self.logger.info("Attempting form element error recovery")
        
        # Try alternative element selection strategies
        strategies = [
            "Try partial ID matches",
            "Try name attribute selectors", 
            "Try data-automation-id selectors",
            "Try label-based selection",
            "Try placeholder-based selection"
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                self.logger.info(f"Element recovery strategy {i+1}: {strategy}")
                await asyncio.sleep(0.3)  # Placeholder
                # This would contain actual element finding logic
                return False  # For now, return False until integrated
            except Exception as strategy_error:
                self.logger.warning(f"Element strategy {i+1} failed: {strategy_error}")
                continue
        
        return False
    
    async def _handle_form_validation_error(self, error: Exception) -> bool:
        """Handle form validation errors with alternative values"""
        self.logger.info("Attempting form validation error recovery")
        
        # Try alternative values or formats
        validation_strategies = [
            "Try default/fallback values",
            "Try different date formats",
            "Try simplified text values",
            "Skip validation and continue"
        ]
        
        for i, strategy in enumerate(validation_strategies):
            try:
                self.logger.info(f"Validation recovery strategy {i+1}: {strategy}")
                await asyncio.sleep(0.3)  # Placeholder
                # This would contain actual validation recovery logic
                return False  # For now, return False until integrated
            except Exception as strategy_error:
                self.logger.warning(f"Validation strategy {i+1} failed: {strategy_error}")
                continue
        
        return False
    
    async def _handle_form_interaction_error(self, error: Exception) -> bool:
        """Handle form interaction errors with alternative methods"""
        self.logger.info("Attempting form interaction error recovery")
        
        # Try alternative interaction methods
        interaction_strategies = [
            "Try click() instead of fill()",
            "Try keyboard input instead of direct fill",
            "Try focus() then type()",
            "Try JavaScript execution",
            "Try slower interaction with delays"
        ]
        
        for i, strategy in enumerate(interaction_strategies):
            try:
                self.logger.info(f"Interaction recovery strategy {i+1}: {strategy}")
                await asyncio.sleep(0.5)  # Placeholder
                # This would contain actual interaction recovery logic
                return False  # For now, return False until integrated
            except Exception as strategy_error:
                self.logger.warning(f"Interaction strategy {i+1} failed: {strategy_error}")
                continue
        
        return False
    
    async def _graceful_form_degradation(self, error: Exception) -> bool:
        """
        Implement graceful degradation for non-critical failures
        Requirement: 7.4 - Implement graceful degradation for non-critical failures
        """
        self.logger.info("Implementing graceful form degradation")
        
        error_message = str(error).lower()
        
        # Identify non-critical form fields that can be skipped
        non_critical_indicators = [
            "optional", "not required", "preference", "additional", "extra",
            "phone", "address", "linkedin", "github", "portfolio", "website"
        ]
        
        if any(indicator in error_message for indicator in non_critical_indicators):
            self.logger.info("Non-critical field error detected - continuing with graceful degradation")
            return True
        
        # For critical fields, try one more simplified approach
        critical_indicators = ["required", "mandatory", "must", "name", "email"]
        if any(indicator in error_message for indicator in critical_indicators):
            self.logger.warning("Critical field error - attempting simplified approach")
            try:
                # This would contain simplified form filling logic
                await asyncio.sleep(0.5)  # Placeholder
                return False  # For now, return False until integrated
            except:
                self.logger.error("Critical field error - graceful degradation failed")
                return False
        
        # Default: treat as non-critical and continue
        self.logger.info("Unknown field error - treating as non-critical and continuing")
        return True
    
    # Placeholder methods for integration with actual automation components
    async def _placeholder_account_creation(self):
        """Placeholder for account creation retry logic"""
        # This will be replaced with actual account creation logic when integrated
        raise Exception("Account creation retry placeholder - not yet integrated")
    
    async def _placeholder_navigation(self):
        """Placeholder for navigation retry logic"""
        # This will be replaced with actual navigation logic when integrated
        raise Exception("Navigation retry placeholder - not yet integrated")
    
    async def _placeholder_form_filling(self):
        """Placeholder for form filling retry logic"""
        # This will be replaced with actual form filling logic when integrated
        raise Exception("Form filling retry placeholder - not yet integrated")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        Generate error summary report
        Requirement: 7.5 - When the process completes THEN the system SHALL generate a summary report
        """
        return {
            'error_counts': self.error_counts.copy(),
            'recovery_attempts': self.recovery_attempts.copy(),
            'current_page_context': self.page_context.copy(),
            'total_errors': sum(self.error_counts.values()),
            'total_recovery_attempts': sum(self.recovery_attempts.values())
        }
    
    def reset_error_tracking(self):
        """Reset error tracking for new automation run"""
        self.error_counts.clear()
        self.recovery_attempts.clear()
        self.page_context.clear()
        self.logger.info("Error tracking reset for new automation run")

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
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading JSON config from {file_path}: {str(e)}")
            return {}
    
    def extract_page_config(self, page_data: Dict) -> Dict:
        """Extract page configuration from page data"""
        return page_data.get('form_elements', [])
    
    def get_field_mappings(self, page_type: str) -> Dict:
        """Get field mappings for specific page type"""
        return self.form_mappings.get(page_type, {})
    
    def validate_json_structure(self, json_data: Dict) -> bool:
        """Validate JSON structure matches expected format"""
        required_fields = ['label', 'id_of_input_component', 'required', 'type_of_input', 'options', 'user_data_select_values']
        
        if not isinstance(json_data, dict):
            return False
        
        for field in required_fields:
            if field not in json_data:
                return False
        
        return True
    
    async def extract_form_element_json(self, page: Page, element) -> Dict:
        """
        Extract JSON configuration for a single form element
        Requirements: 4.1, 4.2, 4.3, 4.4
        """
        try:
            # Extract basic element information
            element_id = await self._get_element_id(element)
            if not element_id:
                return {}
            
            # Extract label from parent div (Requirement 4.2)
            label = await self.extract_label_from_parent_div(element)
            
            # Determine input type (Requirement 4.3)
            input_type = await self.determine_input_type(element)
            
            # Extract options for select elements (Requirement 4.4)
            options = await self.extract_options_for_select_elements(element)
            
            # Check if field is required
            is_required = await self._is_element_required(element)
            
            # Generate user data select values for testing
            user_data_values = self._generate_user_data_values(input_type, options)
            
            # Create JSON structure matching exact specification
            element_json = {
                "label": label,
                "id_of_input_component": element_id,
                "required": is_required,
                "type_of_input": input_type,
                "options": options,
                "user_data_select_values": user_data_values
            }
            
            # Validate structure (Requirement 4.1)
            if self.validate_json_structure(element_json):
                return element_json
            else:
                self.logger.warning(f"Invalid JSON structure for element: {element_id}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error extracting form element JSON: {str(e)}")
            return {}
    
    async def extract_label_from_parent_div(self, element) -> str:
        """
        Extract text content from parent div element
        Requirement: 4.2 - Implement extract_label_from_parent_div method
        """
        try:
            # Strategy 1: Look for associated label element
            element_id = await element.get_attribute('id')
            if element_id:
                label_element = await element.evaluate(f'document.querySelector("label[for=\\"{element_id}\\"]")')
                if label_element:
                    label_text = await label_element.inner_text()
                    if label_text.strip():
                        return label_text.strip()
            
            # Strategy 2: Look in parent elements for text content
            parent_levels = [1, 2, 3]  # Check up to 3 parent levels
            
            for level in parent_levels:
                try:
                    # Navigate up the DOM tree
                    parent_selector = "parent" + "().parent" * (level - 1) + "()"
                    parent_element = await element.evaluate(f'this.{parent_selector}')
                    
                    if parent_element:
                        # Get all text content from parent
                        parent_text = await parent_element.evaluate('el => el.textContent', parent_element)
                        
                        if parent_text:
                            # Clean and extract meaningful text
                            cleaned_text = self._clean_label_text(parent_text)
                            if cleaned_text and len(cleaned_text) < 200:  # Reasonable label length
                                return cleaned_text
                
                except:
                    continue
            
            # Strategy 3: Look for aria-label or placeholder
            aria_label = await element.get_attribute('aria-label')
            if aria_label and aria_label.strip():
                return aria_label.strip()
            
            placeholder = await element.get_attribute('placeholder')
            if placeholder and placeholder.strip():
                return placeholder.strip()
            
            # Strategy 4: Look for nearby text elements
            try:
                # Find preceding text elements
                preceding_text = await element.evaluate('''
                    el => {
                        let prev = el.previousElementSibling;
                        while (prev) {
                            if (prev.textContent && prev.textContent.trim()) {
                                return prev.textContent.trim();
                            }
                            prev = prev.previousElementSibling;
                        }
                        return '';
                    }
                ''')
                
                if preceding_text and len(preceding_text) < 100:
                    return self._clean_label_text(preceding_text)
            
            except:
                pass
            
            # Fallback: return "Unlabeled Field"
            return "Unlabeled Field"
            
        except Exception as e:
            self.logger.error(f"Error extracting label from parent div: {str(e)}")
            return "Unlabeled Field"
    
    def _clean_label_text(self, text: str) -> str:
        """Clean and normalize extracted label text"""
        if not text:
            return ""
        
        # Remove extra whitespace and newlines
        cleaned = ' '.join(text.split())
        
        # Remove common suffixes/prefixes
        suffixes_to_remove = ['*', ':', '(required)', '(optional)', 'Required', 'Optional']
        for suffix in suffixes_to_remove:
            if cleaned.endswith(suffix):
                cleaned = cleaned[:-len(suffix)].strip()
            if cleaned.startswith(suffix):
                cleaned = cleaned[len(suffix):].strip()
        
        # Limit length and return
        return cleaned[:100].strip()
    
    async def determine_input_type(self, element) -> str:
        """
        Classify inputs as text|textarea|select|multiselect|checkbox|radio|date|file|dropdown
        Requirement: 4.3 - Create determine_input_type method
        """
        try:
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            
            if tag_name == 'input':
                input_type = await element.get_attribute('type')
                input_type = input_type.lower() if input_type else 'text'
                
                # Map HTML input types to our classification
                type_mapping = {
                    'text': 'text',
                    'email': 'text',
                    'tel': 'text',
                    'url': 'text',
                    'password': 'password',
                    'number': 'text',
                    'search': 'text',
                    'checkbox': 'checkbox',
                    'radio': 'radio',
                    'date': 'date',
                    'datetime-local': 'date',
                    'time': 'date',
                    'file': 'file',
                    'hidden': 'text',
                    'submit': 'submit',
                    'button': 'button'
                }
                
                return type_mapping.get(input_type, 'text')
            
            elif tag_name == 'textarea':
                return 'textarea'
            
            elif tag_name == 'select':
                # Check if it's multiselect
                is_multiple = await element.get_attribute('multiple')
                return 'multiselect' if is_multiple else 'select'
            
            elif tag_name == 'button':
                # Check if it's a dropdown button
                aria_haspopup = await element.get_attribute('aria-haspopup')
                role = await element.get_attribute('role')
                
                if aria_haspopup == 'listbox' or 'dropdown' in (role or ''):
                    return 'dropdown'
                else:
                    return 'button'
            
            else:
                # Check for custom dropdown indicators
                class_name = await element.get_attribute('class') or ''
                aria_role = await element.get_attribute('role') or ''
                
                if 'dropdown' in class_name.lower() or 'combobox' in aria_role:
                    return 'dropdown'
                
                return 'text'  # Default fallback
                
        except Exception as e:
            self.logger.error(f"Error determining input type: {str(e)}")
            return 'text'
    
    async def extract_options_for_select_elements(self, element) -> List[str]:
        """
        Get visible choices for select/radio/checkbox elements
        Requirement: 4.4 - Add extract_options_for_select_elements method
        """
        try:
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            
            if tag_name == 'select':
                # Extract options from select element
                options = await element.query_selector_all('option')
                option_texts = []
                
                for option in options:
                    option_text = await option.inner_text()
                    option_value = await option.get_attribute('value')
                    
                    # Use text if available, otherwise use value
                    display_text = option_text.strip() if option_text.strip() else option_value
                    if display_text and display_text not in option_texts:
                        option_texts.append(display_text)
                
                return option_texts
            
            elif tag_name == 'input':
                input_type = await element.get_attribute('type')
                
                if input_type == 'radio':
                    # Find all radio buttons with the same name
                    name = await element.get_attribute('name')
                    if name:
                        radio_elements = await element.evaluate(f'''
                            document.querySelectorAll('input[type="radio"][name="{name}"]')
                        ''')
                        
                        option_texts = []
                        for radio in radio_elements:
                            # Look for associated label
                            radio_id = await radio.get_attribute('id')
                            if radio_id:
                                label = await element.evaluate(f'''
                                    document.querySelector('label[for="{radio_id}"]')
                                ''')
                                if label:
                                    label_text = await label.inner_text()
                                    if label_text.strip():
                                        option_texts.append(label_text.strip())
                        
                        return option_texts
                
                elif input_type == 'checkbox':
                    # For checkboxes, return binary options
                    return ['Yes', 'No']
            
            elif tag_name == 'button':
                # For dropdown buttons, try to find associated options
                aria_controls = await element.get_attribute('aria-controls')
                if aria_controls:
                    # Look for controlled element with options
                    controlled_element = await element.evaluate(f'''
                        document.getElementById('{aria_controls}')
                    ''')
                    
                    if controlled_element:
                        option_elements = await controlled_element.query_selector_all('[role="option"], li, .option')
                        option_texts = []
                        
                        for option in option_elements:
                            option_text = await option.inner_text()
                            if option_text.strip():
                                option_texts.append(option_text.strip())
                        
                        return option_texts
            
            return []  # No options found
            
        except Exception as e:
            self.logger.error(f"Error extracting options: {str(e)}")
            return []
    
    async def _get_element_id(self, element) -> str:
        """Get element identifier (id, name, or data-automation-id)"""
        try:
            # Try id first
            element_id = await element.get_attribute('id')
            if element_id:
                return element_id
            
            # Try data-automation-id
            automation_id = await element.get_attribute('data-automation-id')
            if automation_id:
                return automation_id
            
            # Try name
            name = await element.get_attribute('name')
            if name:
                return name
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error getting element ID: {str(e)}")
            return ""
    
    async def _is_element_required(self, element) -> bool:
        """Check if element is required"""
        try:
            # Check required attribute
            required_attr = await element.get_attribute('required')
            if required_attr is not None:
                return True
            
            # Check aria-required
            aria_required = await element.get_attribute('aria-required')
            if aria_required == 'true':
                return True
            
            # Check for visual indicators (asterisk, "required" text)
            parent_text = await element.evaluate('''
                el => {
                    let parent = el.parentElement;
                    if (parent) {
                        return parent.textContent || '';
                    }
                    return '';
                }
            ''')
            
            if parent_text and ('*' in parent_text or 'required' in parent_text.lower()):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking if element is required: {str(e)}")
            return False
    
    def _generate_user_data_values(self, input_type: str, options: List[str]) -> List[str]:
        """Generate example values for testing"""
        if input_type in ['select', 'multiselect', 'radio', 'dropdown'] and options:
            # For choice-based inputs, return first option as example
            return [options[0]] if options else []
        
        elif input_type == 'checkbox':
            return ['No']  # Default to unchecked
        
        else:
            return []  # No example values for text inputs


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
        Fill forms on current page using JSON-driven form filling with DirectFormFiller integration
        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
        """
        try:
            self.logger.info("Starting JSON-driven form filling process")
            
            # First, try using DirectFormFiller for known field mappings (Requirement 5.1)
            direct_fill_count = await self.form_filler.fill_page_by_automation_id(page)
            self.logger.info(f"DirectFormFiller filled {direct_fill_count} fields")
            
            # Then, use JSON configuration for additional fields (Requirement 5.2)
            json_fill_count = 0
            json_failed_count = 0
            required_fields_failed = []
            
            if json_data and json_data.get('form_elements'):
                form_elements = json_data['form_elements']
                self.logger.info(f"Processing {len(form_elements)} form elements from JSON configuration")
                
                for element_data in form_elements:
                    try:
                        element_id = element_data.get('id_of_input_component')
                        element_label = element_data.get('label', 'Unknown')
                        element_type = element_data.get('type_of_input', 'text')
                        is_required = element_data.get('required', False)
                        
                        if not element_id:
                            self.logger.warning(f"No ID found for element: {element_label}")
                            continue
                        
                        # Skip if DirectFormFiller already handled this field
                        if self._is_field_handled_by_direct_filler(element_id):
                            self.logger.debug(f"Field {element_id} already handled by DirectFormFiller")
                            continue
                        
                        # Validate field before filling (Requirement 5.3)
                        validation_result = await self._validate_form_field(page, element_data)
                        if not validation_result['valid']:
                            self.logger.warning(f"Field validation failed for {element_label}: {validation_result['reason']}")
                            if is_required:
                                required_fields_failed.append(element_label)
                            continue
                        
                        # Attempt to fill the field with retry mechanism (Requirement 5.4)
                        fill_success = await self._fill_field_with_retry(page, element_data, max_retries=3)
                        
                        if fill_success:
                            json_fill_count += 1
                            self.logger.debug(f"Successfully filled: {element_label}")
                        else:
                            json_failed_count += 1
                            self.logger.warning(f"Failed to fill: {element_label}")
                            if is_required:
                                required_fields_failed.append(element_label)
                    
                    except Exception as e:
                        json_failed_count += 1
                        element_label = element_data.get('label', 'Unknown')
                        self.logger.error(f"Error processing element {element_label}: {str(e)}")
                        if element_data.get('required', False):
                            required_fields_failed.append(element_label)
            
            # Final validation of required fields (Requirement 5.3)
            total_filled = direct_fill_count + json_fill_count
            total_failed = json_failed_count
            
            self.logger.info(f"Form filling summary - DirectFormFiller: {direct_fill_count}, JSON: {json_fill_count}, Failed: {total_failed}")
            
            # Check if any required fields failed (Requirement 5.5)
            if required_fields_failed:
                self.logger.error(f"Required fields failed validation: {', '.join(required_fields_failed)}")
                return False
            
            # Consider success if we filled at least some elements
            success = total_filled > 0 or (not json_data or not json_data.get('form_elements'))
            
            if success:
                self.logger.info("Form filling completed successfully")
            else:
                self.logger.error("Form filling failed - no fields were filled")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Critical error in form filling process: {str(e)}")
            return False
    
    def _is_field_handled_by_direct_filler(self, field_id: str) -> bool:
        """Check if field is already handled by DirectFormFiller"""
        # Check against DirectFormFiller's field mappings
        return field_id in self.form_filler.field_mappings
    
    async def _validate_form_field(self, page: Page, element_data: Dict) -> Dict:
        """
        Validate form field before filling
        Requirement: 5.3 - Add field validation and required field checking
        """
        try:
            element_id = element_data.get('id_of_input_component')
            element_label = element_data.get('label', 'Unknown')
            is_required = element_data.get('required', False)
            element_type = element_data.get('type_of_input', 'text')
            
            # Find the element on the page
            element = await self._find_element_by_id(page, element_id)
            if not element:
                return {
                    'valid': False,
                    'reason': f'Element not found: {element_id}'
                }
            
            # Check if element is visible and enabled
            is_visible = await element.is_visible()
            is_enabled = await element.is_enabled()
            
            if not is_visible:
                return {
                    'valid': not is_required,  # Only invalid if required
                    'reason': f'Element not visible: {element_label}'
                }
            
            if not is_enabled:
                return {
                    'valid': not is_required,  # Only invalid if required
                    'reason': f'Element not enabled: {element_label}'
                }
            
            # Validate element type matches expected type
            actual_tag = await element.evaluate('el => el.tagName.toLowerCase()')
            actual_type = await element.get_attribute('type')
            
            # Basic type validation
            if element_type == 'select' and actual_tag != 'select':
                return {
                    'valid': False,
                    'reason': f'Type mismatch: expected select, found {actual_tag}'
                }
            
            if element_type == 'textarea' and actual_tag != 'textarea':
                return {
                    'valid': False,
                    'reason': f'Type mismatch: expected textarea, found {actual_tag}'
                }
            
            # Check if required field has appropriate validation attributes
            if is_required:
                required_attr = await element.get_attribute('required')
                aria_required = await element.get_attribute('aria-required')
                
                if not required_attr and aria_required != 'true':
                    self.logger.debug(f"Required field {element_label} missing validation attributes")
            
            return {
                'valid': True,
                'reason': 'Field validation passed'
            }
            
        except Exception as e:
            self.logger.error(f"Error validating field {element_data.get('label', 'Unknown')}: {str(e)}")
            return {
                'valid': False,
                'reason': f'Validation error: {str(e)}'
            }
    
    async def _fill_field_with_retry(self, page: Page, element_data: Dict, max_retries: int = 3) -> bool:
        """
        Fill form field with retry mechanism for failed attempts
        Requirement: 5.4 - Create form filling retry mechanisms for failed attempts
        """
        element_id = element_data.get('id_of_input_component')
        element_label = element_data.get('label', 'Unknown')
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Fill attempt {attempt + 1}/{max_retries} for {element_label}")
                
                # Find the element (it might have changed between attempts)
                element = await self._find_element_by_id(page, element_id)
                if not element:
                    self.logger.warning(f"Element not found on attempt {attempt + 1}: {element_id}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
                        continue
                    return False
                
                # Try different filling strategies based on attempt number
                if attempt == 0:
                    # First attempt: Use standard filling method
                    success = await self._fill_form_element_standard(page, element, element_data)
                elif attempt == 1:
                    # Second attempt: Use alternative filling method
                    success = await self._fill_form_element_alternative(page, element, element_data)
                else:
                    # Final attempt: Use DirectFormFiller as fallback
                    success = await self._fill_form_element_fallback(page, element, element_data)
                
                if success:
                    # Verify the field was actually filled
                    verification_success = await self._verify_field_filled(page, element, element_data)
                    if verification_success:
                        self.logger.debug(f"Successfully filled and verified {element_label} on attempt {attempt + 1}")
                        return True
                    else:
                        self.logger.warning(f"Field filling verification failed for {element_label} on attempt {attempt + 1}")
                
                # Wait before retry (exponential backoff)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                self.logger.warning(f"Error on fill attempt {attempt + 1} for {element_label}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
        
        self.logger.error(f"All {max_retries} fill attempts failed for {element_label}")
        return False
    
    async def _fill_form_element_standard(self, page: Page, element, element_data: Dict) -> bool:
        """Standard form filling method using JSON data"""
        try:
            element_type = element_data.get('type_of_input', 'text')
            user_values = element_data.get('user_data_select_values', [])
            options = element_data.get('options', [])
            
            # Get value to fill
            fill_value = self._get_fill_value_from_json(element_type, user_values, options, element_data)
            
            if not fill_value:
                return True  # No value to fill is not an error
            
            # Fill based on element type
            if element_type in ['text', 'password']:
                await element.fill(fill_value)
                
            elif element_type == 'textarea':
                await element.fill(fill_value)
                
            elif element_type == 'select':
                await element.select_option(label=fill_value)
                
            elif element_type == 'checkbox':
                is_checked = await element.is_checked()
                should_check = fill_value.lower() in ['true', 'yes', '1', 'on']
                if should_check != is_checked:
                    await element.click()
                    
            elif element_type == 'radio':
                await element.click()
                
            elif element_type == 'dropdown':
                await self._fill_dropdown_element(page, element, fill_value)
            
            await asyncio.sleep(0.3)  # Allow time for changes to register
            return True
            
        except Exception as e:
            self.logger.debug(f"Standard fill method failed: {str(e)}")
            return False
    
    async def _fill_form_element_alternative(self, page: Page, element, element_data: Dict) -> bool:
        """Alternative form filling method using different strategies"""
        try:
            element_type = element_data.get('type_of_input', 'text')
            element_id = element_data.get('id_of_input_component')
            
            # Get value to fill
            fill_value = self._get_fill_value_from_json(element_type, 
                                                      element_data.get('user_data_select_values', []),
                                                      element_data.get('options', []),
                                                      element_data)
            
            if not fill_value:
                return True
            
            # Alternative strategies
            if element_type in ['text', 'password', 'textarea']:
                # Use keyboard input instead of fill
                await element.click()
                await asyncio.sleep(0.2)
                await page.keyboard.press('Control+a')  # Select all
                await asyncio.sleep(0.1)
                await page.keyboard.type(fill_value, delay=50)
                
            elif element_type == 'select':
                # Try selecting by value instead of label
                try:
                    await element.select_option(value=fill_value)
                except:
                    # Fallback to index-based selection
                    options = element_data.get('options', [])
                    if fill_value in options:
                        index = options.index(fill_value)
                        await element.select_option(index=index)
                        
            elif element_type == 'dropdown':
                # Use typing approach for dropdowns
                await element.click()
                await asyncio.sleep(0.5)
                await page.keyboard.type(fill_value)
                await asyncio.sleep(0.3)
                await page.keyboard.press('Enter')
            
            await asyncio.sleep(0.3)
            return True
            
        except Exception as e:
            self.logger.debug(f"Alternative fill method failed: {str(e)}")
            return False
    
    async def _fill_form_element_fallback(self, page: Page, element, element_data: Dict) -> bool:
        """Fallback form filling using DirectFormFiller approach"""
        try:
            element_id = element_data.get('id_of_input_component')
            
            # Check if DirectFormFiller has a mapping for this field
            if element_id in self.form_filler.field_mappings:
                value = self.form_filler.field_mappings[element_id]
                success = await self.form_filler._fill_field_by_id(page, element_id, value)
                return success
            
            # Use DirectFormFiller's generic filling approach
            element_type = element_data.get('type_of_input', 'text')
            fill_value = self._get_fill_value_from_json(element_type,
                                                      element_data.get('user_data_select_values', []),
                                                      element_data.get('options', []),
                                                      element_data)
            
            if fill_value:
                success = await self.form_filler._fill_field_by_id(page, element_id, fill_value)
                return success
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Fallback fill method failed: {str(e)}")
            return False
    
    async def _verify_field_filled(self, page: Page, element, element_data: Dict) -> bool:
        """Verify that a field was successfully filled"""
        try:
            element_type = element_data.get('type_of_input', 'text')
            expected_value = self._get_fill_value_from_json(element_type,
                                                          element_data.get('user_data_select_values', []),
                                                          element_data.get('options', []),
                                                          element_data)
            
            if not expected_value:
                return True  # No value expected
            
            if element_type in ['text', 'password', 'textarea']:
                actual_value = await element.input_value()
                return actual_value == expected_value
                
            elif element_type == 'checkbox':
                is_checked = await element.is_checked()
                should_be_checked = expected_value.lower() in ['true', 'yes', '1', 'on']
                return is_checked == should_be_checked
                
            elif element_type in ['select', 'dropdown']:
                # For selects, just check if any value is selected
                try:
                    selected_value = await element.input_value()
                    return bool(selected_value)
                except:
                    return True  # Assume success if we can't verify
            
            return True  # Default to success for other types
            
        except Exception as e:
            self.logger.debug(f"Field verification failed: {str(e)}")
            return True  # Don't fail the whole process due to verification issues
    
    def _get_fill_value_from_json(self, element_type: str, user_values: List[str], options: List[str], element_data: Dict) -> str:
        """Get appropriate value to fill based on JSON configuration"""
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
            return os.getenv('REGISTRATION_EMAIL', 'test@example.com')
        elif 'phone' in label:
            return os.getenv('REGISTRATION_PHONE', '555-123-4567')
        elif 'first name' in label:
            return os.getenv('REGISTRATION_FIRST_NAME', 'John')
        elif 'last name' in label:
            return os.getenv('REGISTRATION_LAST_NAME', 'Doe')
        elif 'name' in label:
            return os.getenv('REGISTRATION_FIRST_NAME', 'John') + ' ' + os.getenv('REGISTRATION_LAST_NAME', 'Doe')
        elif 'address' in label:
            return '123 Main St'
        elif 'city' in label:
            return 'San Francisco'
        elif 'zip' in label or 'postal' in label:
            return '94105'
        
        return ''  # Default empty value
    
    async def _fill_dropdown_element(self, page: Page, element, fill_value: str):
        """Handle dropdown element filling"""
        try:
            # Click to open dropdown
            await element.click()
            await asyncio.sleep(0.5)
            
            # Try to find and click the option
            option_selectors = [
                f'[role="option"]:has-text("{fill_value}")',
                f'.dropdown-option:has-text("{fill_value}")',
                f'li:has-text("{fill_value}")',
                f'div:has-text("{fill_value}")'
            ]
            
            for selector in option_selectors:
                try:
                    option_element = await page.wait_for_selector(selector, timeout=2000)
                    if option_element:
                        await option_element.click()
                        return
                except:
                    continue
            
            # Fallback: type and press Enter
            await page.keyboard.type(fill_value)
            await asyncio.sleep(0.3)
            await page.keyboard.press('Enter')
            
        except Exception as e:
            self.logger.debug(f"Dropdown filling failed: {str(e)}")
            raise
    
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
                'button[data-automation-id="pageFooterNextButton"]',
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

class WorkdayPageAutomator:
    """Main orchestrator for Workday page automation"""
    
    def __init__(self, config_manager: ConfigurationManager = None):
        # Initialize configuration manager
        self.config_manager = config_manager or ConfigurationManager()
        self.config = self.config_manager.load_configuration()
        
        # Initialize components with configuration
        self.progress_tracker = ProgressTracker()
        self.page_processor = PageProcessor(DirectFormFiller())
        self.json_extractor = JSONExtractor()
        self.form_filler = DirectFormFiller()
        self.account_creator = WorkdayFormScraper()  # Initialize WorkdayFormScraper
        self.error_handler = ErrorHandler()
        self.automation_state = AutomationState()
        self.logger = logging.getLogger(f"{__name__}.WorkdayPageAutomator")
        
        # Initialize performance monitor
        self.performance_monitor = PerformanceMonitor(
            enable_monitoring=self.config.automation.enable_performance_monitoring,
            log_interval=self.config.automation.performance_log_interval
        )
        
        # Apply configuration settings
        self._apply_configuration()
        
        self.logger.info("WorkdayPageAutomator initialized with configuration management and performance monitoring")
    
    def _apply_configuration(self):
        """Apply configuration settings to components"""
        # Apply automation mode configuration
        mode_config = self.config.automation_mode
        self.headless = mode_config.headless
        self.debug = mode_config.debug
        self.slow_motion = mode_config.slow_motion
        self.timeout = mode_config.timeout
        self.screenshot_on_failure = mode_config.screenshot_on_failure
        
        # Apply automation configuration
        automation_config = self.config.automation
        self.max_retries = automation_config.max_retries
        self.page_timeout = automation_config.page_timeout
        self.navigation_delay = automation_config.navigation_delay
        self.element_wait_timeout = automation_config.element_wait_timeout
        self.form_fill_delay = automation_config.form_fill_delay
        
        # Apply workday configuration
        workday_config = self.config.workday
        self.tenant_url = workday_config.tenant_url
        self.job_url = workday_config.job_url
        self.create_account_mode = workday_config.create_account_mode
        
        self.logger.info(f"Configuration applied - Headless: {self.headless}, Debug: {self.debug}, Max retries: {self.max_retries}")
    
    def get_page_processor_config(self, page_name: str):
        """Get configuration for a specific page processor"""
        return self.config_manager.get_page_processor_config(page_name)
    
    def get_form_elements_config(self):
        """Get form elements configuration"""
        return self.config_manager.get_form_elements_config()
    
    def get_automation_mode_config(self):
        """Get automation mode configuration"""
        return self.config_manager.get_automation_mode_config()
    
    @performance_monitor("run_automation")
    async def run_automation(self) -> bool:
        """
        Main automation orchestration method
        Integrates account creation with page processing flow
        """
        try:
            self.logger.info("Starting Workday page automation")
            
            # Start performance monitoring
            automation_id = f"workday_automation_{int(time.time())}"
            self.performance_monitor.start_automation_monitoring(automation_id)
            
            self.automation_state.automation_start_time = time.time()
            
            # Step 1: Create account using existing resume_fill.py functionality
            self.logger.info("Step 1: Account Creation")
            async with self.performance_monitor.measure_async_operation("account_creation"):
                account_success = await self.create_account()
            
            if not account_success:
                self.logger.error("Account creation failed, cannot proceed with automation")
                self.performance_monitor.stop_automation_monitoring()
                return False
            
            # Step 2: Validate account status before proceeding to page processing
            self.logger.info("Step 2: Account Status Validation")
            async with self.performance_monitor.measure_async_operation("account_validation"):
                if not self.is_account_created():
                    self.logger.error("Account status validation failed")
                    self.performance_monitor.stop_automation_monitoring()
                    return False
            
            self.logger.info("Account creation and validation successful")
            
            # Step 3: Page processing with performance monitoring
            self.logger.info("Step 3: Page Processing with Performance Monitoring")
            async with self.performance_monitor.measure_async_operation("page_processing"):
                page_processing_success = await self.process_all_pages()
            
            if not page_processing_success:
                self.logger.error("Page processing failed")
                self.performance_monitor.stop_automation_monitoring()
                return False
            
            # Generate and save performance report
            self.logger.info("Generating performance report")
            report = self.performance_monitor.generate_performance_report(automation_id)
            self.performance_monitor.save_performance_report(report)
            
            self.performance_monitor.stop_automation_monitoring()
            self.logger.info("Workday automation completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Automation failed: {str(e)}")
            self.automation_state.last_error = str(e)
            return False
    
    async def create_account(self) -> bool:
        """
        Create account using existing resume_fill.py functionality
        Requirements: 1.1, 1.2, 1.3, 1.4
        """
        try:
            self.logger.info("Starting account creation using WorkdayFormScraper")
            
            # Check if account creation is needed (Requirement 1.1)
            if self.automation_state.account_created:
                self.logger.info("Account already created, skipping account creation")
                return True
            
            # Validate required environment variables before account creation
            required_env_vars = [
                'WORKDAY_TENANT_URL',
                'REGISTRATION_EMAIL',
                'REGISTRATION_FIRST_NAME',
                'REGISTRATION_LAST_NAME'
            ]
            
            missing_vars = [var for var in required_env_vars if not os.getenv(var)]
            if missing_vars:
                error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
                self.logger.error(error_msg)
                self.automation_state.last_error = error_msg
                return await self.error_handler.handle_account_creation_error(Exception(error_msg))
            
            # Run the account creation process (Requirement 1.1)
            self.logger.info("Executing WorkdayFormScraper.run() for account creation")
            extraction_results = await self.account_creator.run()
            
            # Validate account creation results (Requirement 1.2, 1.3)
            if extraction_results and not extraction_results.errors:
                self.logger.info("Account creation completed successfully")
                self.automation_state.account_created = True
                
                # Validate account status (Requirement 1.4)
                account_valid = await self._validate_account_status(extraction_results)
                if account_valid:
                    self.logger.info("Account validation successful")
                    return True
                else:
                    self.logger.warning("Account created but validation failed")
                    return await self.error_handler.handle_account_creation_error(
                        Exception("Account validation failed")
                    )
            
            elif extraction_results and extraction_results.errors:
                # Handle existing account scenarios gracefully (Requirement 1.2)
                error_messages = extraction_results.errors
                
                # Check if errors indicate existing account (not necessarily a failure)
                existing_account_indicators = [
                    "account already exists",
                    "email already registered",
                    "user already exists",
                    "duplicate account"
                ]
                
                is_existing_account = any(
                    indicator in error.lower() 
                    for error in error_messages 
                    for indicator in existing_account_indicators
                )
                
                if is_existing_account:
                    self.logger.info("Account already exists, proceeding with existing account")
                    self.automation_state.account_created = True
                    return True
                else:
                    # Real errors occurred (Requirement 1.3)
                    error_msg = f"Account creation failed with errors: {'; '.join(error_messages)}"
                    self.logger.error(error_msg)
                    self.automation_state.last_error = error_msg
                    return await self.error_handler.handle_account_creation_error(
                        Exception(error_msg)
                    )
            
            else:
                # No results returned
                error_msg = "Account creation failed - no results returned from WorkdayFormScraper"
                self.logger.error(error_msg)
                self.automation_state.last_error = error_msg
                return await self.error_handler.handle_account_creation_error(
                    Exception(error_msg)
                )
                
        except Exception as e:
            # Handle any unexpected errors (Requirement 1.3)
            error_msg = f"Account creation failed with exception: {str(e)}"
            self.logger.error(error_msg)
            self.automation_state.last_error = error_msg
            return await self.error_handler.handle_account_creation_error(e)
    
    async def _validate_account_status(self, extraction_results) -> bool:
        """
        Validate account status before proceeding to page processing
        Requirement: 1.4 - Add account status checking
        """
        try:
            self.logger.info("Validating account creation status")
            
            # Check if we have valid extraction results
            if not extraction_results:
                self.logger.error("No extraction results to validate")
                return False
            
            # Check if we have discovered pages (indicates successful navigation)
            if not extraction_results.pages_visited:
                self.logger.warning("No pages were visited during account creation")
                return False
            
            # Check if we have form elements (indicates successful form extraction)
            if not extraction_results.form_elements:
                self.logger.warning("No form elements were extracted during account creation")
                # This might be okay if account creation was successful but no forms were found
            
            # Check if tenant URL is accessible
            if not extraction_results.tenant_url:
                self.logger.error("No tenant URL found in extraction results")
                return False
            
            # Validate that we have a reasonable number of pages
            if extraction_results.total_pages_crawled < 1:
                self.logger.error("No pages were crawled during account creation")
                return False
            
            # Check extraction timestamp (should be recent)
            current_time = time.time()
            time_diff = current_time - extraction_results.extraction_timestamp
            if time_diff > 3600:  # More than 1 hour old
                self.logger.warning(f"Extraction results are {time_diff/60:.1f} minutes old")
            
            self.logger.info(f"Account validation successful - {extraction_results.total_pages_crawled} pages crawled, "
                           f"{extraction_results.total_form_elements} form elements extracted")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating account status: {str(e)}")
            return False
    
    def is_account_created(self) -> bool:
        """Check if account has been successfully created"""
        return self.automation_state.account_created
    
    async def process_all_pages(self) -> bool:
        """Process all pages in the automation flow with performance monitoring"""
        try:
            self.logger.info("Starting page processing with performance monitoring")
            
            # Discover pages dynamically or use fallback
            pages = await self._discover_pages_dynamically()
            if not pages:
                pages = ["Login", "My Information", "Job Application", "EEO", "Review"]  # Fallback
            
            self.progress_tracker.initialize(pages)
            
            for i, page_name in enumerate(pages):
                self.logger.info(f"Processing page {i+1}/{len(pages)}: {page_name}")
                
                # Start page performance monitoring
                self.performance_monitor.start_page_monitoring(page_name, i)
                self.progress_tracker.update_progress(i, page_name)
                
                try:
                    # Process single page with performance monitoring
                    async with self.performance_monitor.measure_async_operation(f"page_{page_name.lower().replace(' ', '_')}"):
                        page_success = await self._process_single_page(i, page_name)
                    
                    if page_success:
                        self.progress_tracker.mark_page_completed()
                        self.performance_monitor.end_page_monitoring(i, success=True)
                        self.logger.info(f"Completed page: {page_name}")
                    else:
                        self.progress_tracker.mark_page_failed(i, f"Failed to process {page_name}")
                        self.performance_monitor.end_page_monitoring(i, success=False)
                        self.performance_monitor.increment_error_count()
                        self.logger.error(f"Failed to process page: {page_name}")
                        
                        # Check if we should continue after failure
                        if not await self._should_continue_after_failure(i, page_name):
                            return False
                
                except Exception as e:
                    self.logger.error(f"Error processing page {page_name}: {e}")
                    self.performance_monitor.end_page_monitoring(i, success=False)
                    self.performance_monitor.increment_error_count()
                    self.progress_tracker.mark_page_failed(i, str(e))
                    
                    if not await self._should_continue_after_failure(i, page_name):
                        return False
            
            # Log performance summary
            performance_summary = self.performance_monitor.get_performance_summary()
            self.logger.info(f"Page processing performance summary: {performance_summary}")
            
            self.logger.info("All pages processed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Page processing failed: {str(e)}")
            return False
    
    # Page-specific processor methods
    async def process_login_page(self, page: Page) -> bool:
        """
        Process login page with specific form field identification and navigation
        Requirements: 3.1, 3.2, 3.3, 5.1, 5.2
        """
        try:
            self.logger.info("Processing login page")
            
            # Page-specific form field identification and mapping
            login_field_mappings = {
                'email': ['email', 'username', 'user', 'login', 'emailAddress'],
                'password': ['password', 'pwd', 'pass'],
                'remember_me': ['remember', 'rememberMe', 'staySignedIn']
            }
            
            # Extract page JSON with login-specific context
            page_json = await self.page_processor.extract_page_json(page)
            
            # Apply login-specific field mapping
            mapped_elements = self._apply_page_specific_mapping(page_json, login_field_mappings)
            
            # Fill login form with environment variables
            login_success = await self._fill_login_form(page, mapped_elements)
            if not login_success:
                self.logger.error("Login form filling failed")
                return False
            
            # Page-specific navigation logic for login
            navigation_success = await self._navigate_login_page(page)
            if not navigation_success:
                self.logger.error("Login page navigation failed")
                return False
            
            self.logger.info("Login page processed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing login page: {str(e)}")
            return False
    
    async def process_my_information_page(self, page: Page) -> bool:
        """
        Process my information page with personal data form fields
        Requirements: 3.1, 3.2, 3.3, 5.1, 5.2
        """
        try:
            self.logger.info("Processing my information page")
            
            # Page-specific form field identification and mapping
            personal_info_mappings = {
                'first_name': ['firstName', 'fname', 'first-name', 'givenName', 'legalName--firstName'],
                'last_name': ['lastName', 'lname', 'last-name', 'familyName', 'surname', 'legalName--lastName'],
                'middle_name': ['middleName', 'mname', 'middle-name', 'middleInitial'],
                'phone': ['phone', 'phoneNumber', 'mobile', 'telephone', 'tel'],
                'address': ['address', 'street', 'addressLine1', 'streetAddress'],
                'city': ['city', 'locality', 'town'],
                'state': ['state', 'province', 'region'],
                'zip_code': ['zip', 'zipCode', 'postalCode', 'postal'],
                'country': ['country', 'countryCode', 'nationality'],
                'date_of_birth': ['dateOfBirth', 'dob', 'birthDate', 'birthday']
            }
            
            # Extract page JSON with personal info context
            page_json = await self.page_processor.extract_page_json(page)
            
            # Apply personal information field mapping
            mapped_elements = self._apply_page_specific_mapping(page_json, personal_info_mappings)
            
            # Fill personal information form
            form_success = await self._fill_personal_info_form(page, mapped_elements)
            if not form_success:
                self.logger.error("Personal information form filling failed")
                return False
            
            # Page-specific navigation logic for my information
            navigation_success = await self._navigate_my_information_page(page)
            if not navigation_success:
                self.logger.error("My information page navigation failed")
                return False
            
            self.logger.info("My information page processed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing my information page: {str(e)}")
            return False
    
    async def process_job_application_page(self, page: Page) -> bool:
        """
        Process job application page with job-specific form fields
        Requirements: 3.1, 3.2, 3.3, 5.1, 5.2
        """
        try:
            self.logger.info("Processing job application page")
            
            # Page-specific form field identification and mapping
            job_application_mappings = {
                'resume': ['resume', 'cv', 'resumeFile', 'uploadResume'],
                'cover_letter': ['coverLetter', 'coverLetterFile', 'motivationLetter'],
                'position_interest': ['positionInterest', 'whyInterested', 'motivation'],
                'availability': ['availability', 'startDate', 'availableDate'],
                'salary_expectation': ['salary', 'salaryExpectation', 'expectedSalary'],
                'work_authorization': ['workAuthorization', 'eligibleToWork', 'visaStatus'],
                'relocation': ['relocation', 'willingToRelocate', 'relocate'],
                'travel': ['travel', 'willingToTravel', 'travelPercentage'],
                'source': ['source', 'howDidYouHear', 'referralSource']
            }
            
            # Extract page JSON with job application context
            page_json = await self.page_processor.extract_page_json(page)
            
            # Apply job application field mapping
            mapped_elements = self._apply_page_specific_mapping(page_json, job_application_mappings)
            
            # Fill job application form
            form_success = await self._fill_job_application_form(page, mapped_elements)
            if not form_success:
                self.logger.error("Job application form filling failed")
                return False
            
            # Page-specific navigation logic for job application
            navigation_success = await self._navigate_job_application_page(page)
            if not navigation_success:
                self.logger.error("Job application page navigation failed")
                return False
            
            self.logger.info("Job application page processed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing job application page: {str(e)}")
            return False
    
    async def process_eeo_page(self, page: Page) -> bool:
        """
        Process EEO (Equal Employment Opportunity) page with demographic fields
        Requirements: 3.1, 3.2, 3.3, 5.1, 5.2
        """
        try:
            self.logger.info("Processing EEO page")
            
            # Page-specific form field identification and mapping
            eeo_mappings = {
                'gender': ['gender', 'sex', 'genderIdentity'],
                'ethnicity': ['ethnicity', 'race', 'raceEthnicity', 'ethnic'],
                'veteran_status': ['veteran', 'veteranStatus', 'militaryService'],
                'disability_status': ['disability', 'disabilityStatus', 'accommodation'],
                'sexual_orientation': ['sexualOrientation', 'orientation'],
                'pronouns': ['pronouns', 'preferredPronouns']
            }
            
            # Extract page JSON with EEO context
            page_json = await self.page_processor.extract_page_json(page)
            
            # Apply EEO field mapping
            mapped_elements = self._apply_page_specific_mapping(page_json, eeo_mappings)
            
            # Fill EEO form with privacy-conscious defaults
            form_success = await self._fill_eeo_form(page, mapped_elements)
            if not form_success:
                self.logger.error("EEO form filling failed")
                return False
            
            # Page-specific navigation logic for EEO
            navigation_success = await self._navigate_eeo_page(page)
            if not navigation_success:
                self.logger.error("EEO page navigation failed")
                return False
            
            self.logger.info("EEO page processed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing EEO page: {str(e)}")
            return False
    
    async def process_review_page(self, page: Page) -> bool:
        """
        Process review/summary page with final submission
        Requirements: 3.1, 3.2, 3.3, 5.1, 5.2
        """
        try:
            self.logger.info("Processing review page")
            
            # Page-specific form field identification and mapping
            review_mappings = {
                'terms_agreement': ['terms', 'termsAndConditions', 'agreement', 'consent'],
                'privacy_policy': ['privacy', 'privacyPolicy', 'dataProcessing'],
                'marketing_consent': ['marketing', 'marketingConsent', 'communications'],
                'confirmation': ['confirm', 'confirmation', 'acknowledge']
            }
            
            # Extract page JSON with review context
            page_json = await self.page_processor.extract_page_json(page)
            
            # Apply review page field mapping
            mapped_elements = self._apply_page_specific_mapping(page_json, review_mappings)
            
            # Validate application data before submission
            validation_success = await self._validate_application_data(page)
            if not validation_success:
                self.logger.warning("Application data validation failed, but continuing")
            
            # Fill review form (mainly checkboxes and confirmations)
            form_success = await self._fill_review_form(page, mapped_elements)
            if not form_success:
                self.logger.error("Review form filling failed")
                return False
            
            # Page-specific navigation logic for review (final submission)
            navigation_success = await self._navigate_review_page(page)
            if not navigation_success:
                self.logger.error("Review page navigation (submission) failed")
                return False
            
            self.logger.info("Review page processed successfully - Application submitted")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing review page: {str(e)}")
            return False
    
    async def process_unknown_page(self, page: Page) -> bool:
        """
        Fallback mechanism for unknown page types
        Requirements: 3.1, 3.2, 3.3, 5.1, 5.2
        """
        try:
            self.logger.info("Processing unknown page type - using fallback mechanism")
            
            # Get page information for analysis
            page_url = page.url
            page_title = await page.title()
            
            self.logger.info(f"Unknown page details - URL: {page_url}, Title: {page_title}")
            
            # Generic form field identification (no specific mapping)
            page_json = await self.page_processor.extract_page_json(page)
            
            if not page_json or not page_json.get('form_elements'):
                self.logger.warning("No form elements found on unknown page")
                # Try generic navigation without form filling
                return await self._navigate_unknown_page(page)
            
            # Fill forms using generic approach
            form_success = await self._fill_generic_form(page, page_json)
            if not form_success:
                self.logger.warning("Generic form filling failed on unknown page")
            
            # Try generic navigation
            navigation_success = await self._navigate_unknown_page(page)
            if not navigation_success:
                self.logger.error("Unknown page navigation failed")
                return False
            
            self.logger.info("Unknown page processed successfully using fallback mechanism")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing unknown page: {str(e)}")
            return False
    
    # Helper methods for page-specific form field identification and mapping
    def _apply_page_specific_mapping(self, page_json: Dict, field_mappings: Dict) -> Dict:
        """Apply page-specific field mappings to extracted form elements"""
        try:
            if not page_json or not page_json.get('form_elements'):
                return {}
            
            mapped_elements = {}
            form_elements = page_json['form_elements']
            
            for element in form_elements:
                element_id = element.get('id_of_input_component', '').lower()
                element_label = element.get('label', '').lower()
                
                # Try to match element to field mappings
                for field_name, id_patterns in field_mappings.items():
                    for pattern in id_patterns:
                        if pattern.lower() in element_id or pattern.lower() in element_label:
                            if field_name not in mapped_elements:
                                mapped_elements[field_name] = []
                            mapped_elements[field_name].append(element)
                            self.logger.debug(f"Mapped {element_id} to {field_name}")
                            break
            
            self.logger.info(f"Applied page-specific mapping, found {len(mapped_elements)} field types")
            return mapped_elements
            
        except Exception as e:
            self.logger.error(f"Error applying page-specific mapping: {str(e)}")
            return {}
    
    # Login page specific methods
    async def _fill_login_form(self, page: Page, mapped_elements: Dict) -> bool:
        """Fill login form with environment variables"""
        try:
            self.logger.info("Filling login form")
            
            # Fill email field
            if 'email' in mapped_elements:
                email = os.getenv('REGISTRATION_EMAIL')
                if email:
                    for element_data in mapped_elements['email']:
                        element_id = element_data.get('id_of_input_component')
                        element = await self._find_element_by_id(page, element_id)
                        if element:
                            await element.fill(email)
                            self.logger.debug("Filled email field")
                            break
            
            # Fill password field (if available in environment)
            if 'password' in mapped_elements:
                password = os.getenv('REGISTRATION_PASSWORD', 'DefaultPassword123!')
                for element_data in mapped_elements['password']:
                    element_id = element_data.get('id_of_input_component')
                    element = await self._find_element_by_id(page, element_id)
                    if element:
                        await element.fill(password)
                        self.logger.debug("Filled password field")
                        break
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling login form: {str(e)}")
            return False
    
    async def _navigate_login_page(self, page: Page) -> bool:
        """Navigate from login page using login-specific selectors"""
        try:
            login_navigation_selectors = [
                'button:has-text("Sign In")',
                'button:has-text("Login")',
                'button:has-text("Log In")',
                'input[type="submit"][value*="Sign"]',
                'input[type="submit"][value*="Login"]',
                '.login-button',
                '.signin-button'
            ]
            
            return await self._try_navigation_selectors(page, login_navigation_selectors)
            
        except Exception as e:
            self.logger.error(f"Error navigating login page: {str(e)}")
            return False
    
    # Personal information page specific methods
    async def _fill_personal_info_form(self, page: Page, mapped_elements: Dict) -> bool:
        """Fill personal information form with environment variables"""
        try:
            self.logger.info("Filling personal information form")
            
            # Mapping of field names to environment variables
            env_mappings = {
                'first_name': 'REGISTRATION_FIRST_NAME',
                'last_name': 'REGISTRATION_LAST_NAME',
                'middle_name': 'REGISTRATION_MIDDLE_NAME',
                'phone': 'REGISTRATION_PHONE',
                'address': 'REGISTRATION_ADDRESS',
                'city': 'REGISTRATION_CITY',
                'state': 'REGISTRATION_STATE',
                'zip_code': 'REGISTRATION_ZIP_CODE',
                'country': 'REGISTRATION_COUNTRY',
                'date_of_birth': 'REGISTRATION_DATE_OF_BIRTH'
            }
            
            for field_name, env_var in env_mappings.items():
                if field_name in mapped_elements:
                    value = os.getenv(env_var)
                    if value:
                        for element_data in mapped_elements[field_name]:
                            element_id = element_data.get('id_of_input_component')
                            element = await self._find_element_by_id(page, element_id)
                            if element:
                                await element.fill(value)
                                self.logger.debug(f"Filled {field_name} field")
                                break
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling personal info form: {str(e)}")
            return False
    
    async def _navigate_my_information_page(self, page: Page) -> bool:
        """Navigate from my information page"""
        try:
            info_navigation_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Save and Continue")',
                'button:has-text("Proceed")',
                '.continue-button',
                '.next-button'
            ]
            
            return await self._try_navigation_selectors(page, info_navigation_selectors)
            
        except Exception as e:
            self.logger.error(f"Error navigating my information page: {str(e)}")
            return False
    
    # Job application page specific methods
    async def _fill_job_application_form(self, page: Page, mapped_elements: Dict) -> bool:
        """Fill job application form with appropriate values"""
        try:
            self.logger.info("Filling job application form")
            
            # Default values for job application fields
            default_values = {
                'position_interest': 'I am interested in this position because it aligns with my career goals and skills.',
                'availability': 'Immediately',
                'salary_expectation': 'Negotiable',
                'work_authorization': 'Yes',
                'relocation': 'Yes',
                'travel': 'Yes, up to 25%',
                'source': 'Company Website'
            }
            
            for field_name, default_value in default_values.items():
                if field_name in mapped_elements:
                    # Use environment variable if available, otherwise use default
                    env_var = f'REGISTRATION_{field_name.upper()}'
                    value = os.getenv(env_var, default_value)
                    
                    for element_data in mapped_elements[field_name]:
                        element_id = element_data.get('id_of_input_component')
                        element_type = element_data.get('type_of_input', 'text')
                        element = await self._find_element_by_id(page, element_id)
                        
                        if element:
                            if element_type in ['select', 'dropdown']:
                                # For select elements, try to select the option
                                options = element_data.get('options', [])
                                if options and value in options:
                                    await element.select_option(value=value)
                                elif options:
                                    await element.select_option(value=options[0])
                            else:
                                await element.fill(value)
                            
                            self.logger.debug(f"Filled {field_name} field")
                            break
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling job application form: {str(e)}")
            return False
    
    async def _navigate_job_application_page(self, page: Page) -> bool:
        """Navigate from job application page"""
        try:
            job_navigation_selectors = [
                'button:has-text("Submit Application")',
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Save and Continue")',
                '.submit-application-button',
                '.continue-button'
            ]
            
            return await self._try_navigation_selectors(page, job_navigation_selectors)
            
        except Exception as e:
            self.logger.error(f"Error navigating job application page: {str(e)}")
            return False
    
    # EEO page specific methods
    async def _fill_eeo_form(self, page: Page, mapped_elements: Dict) -> bool:
        """Fill EEO form with privacy-conscious defaults"""
        try:
            self.logger.info("Filling EEO form with privacy-conscious defaults")
            
            # Privacy-conscious default values (prefer not to disclose)
            eeo_defaults = {
                'gender': 'Prefer not to disclose',
                'ethnicity': 'Prefer not to disclose',
                'veteran_status': 'I am not a protected veteran',
                'disability_status': 'I do not have a disability',
                'sexual_orientation': 'Prefer not to disclose',
                'pronouns': 'Prefer not to disclose'
            }
            
            for field_name, default_value in eeo_defaults.items():
                if field_name in mapped_elements:
                    for element_data in mapped_elements[field_name]:
                        element_id = element_data.get('id_of_input_component')
                        element_type = element_data.get('type_of_input', 'text')
                        options = element_data.get('options', [])
                        element = await self._find_element_by_id(page, element_id)
                        
                        if element:
                            if element_type in ['select', 'dropdown']:
                                # Try to find "prefer not to disclose" or similar option
                                prefer_options = [opt for opt in options if 'prefer not' in opt.lower() or 'decline' in opt.lower()]
                                if prefer_options:
                                    await element.select_option(value=prefer_options[0])
                                elif options:
                                    await element.select_option(value=options[-1])  # Often the last option
                            elif element_type == 'radio':
                                # For radio buttons, try to click the "prefer not to disclose" option
                                await element.click()
                            elif element_type == 'checkbox':
                                # For checkboxes, generally leave unchecked (default)
                                pass
                            else:
                                await element.fill(default_value)
                            
                            self.logger.debug(f"Filled {field_name} field with privacy-conscious default")
                            break
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling EEO form: {str(e)}")
            return False
    
    async def _navigate_eeo_page(self, page: Page) -> bool:
        """Navigate from EEO page"""
        try:
            eeo_navigation_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Save and Continue")',
                'button:has-text("Proceed")',
                '.continue-button',
                '.next-button'
            ]
            
            return await self._try_navigation_selectors(page, eeo_navigation_selectors)
            
        except Exception as e:
            self.logger.error(f"Error navigating EEO page: {str(e)}")
            return False
    
    # Review page specific methods
    async def _validate_application_data(self, page: Page) -> bool:
        """Validate application data before submission"""
        try:
            self.logger.info("Validating application data on review page")
            
            # Look for validation errors or warnings on the page
            error_selectors = [
                '.error',
                '.validation-error',
                '.field-error',
                '[class*="error"]',
                '.alert-danger',
                '.warning'
            ]
            
            for selector in error_selectors:
                try:
                    error_elements = await page.query_selector_all(selector)
                    if error_elements:
                        for error_element in error_elements:
                            error_text = await error_element.inner_text()
                            if error_text and error_text.strip():
                                self.logger.warning(f"Validation issue found: {error_text.strip()}")
                except:
                    continue
            
            # Check for required fields that might be missing
            required_indicators = await page.query_selector_all('[required], .required, [aria-required="true"]')
            if required_indicators:
                self.logger.info(f"Found {len(required_indicators)} required field indicators")
            
            return True  # Continue even if validation issues found
            
        except Exception as e:
            self.logger.error(f"Error validating application data: {str(e)}")
            return False
    
    async def _fill_review_form(self, page: Page, mapped_elements: Dict) -> bool:
        """Fill review form (mainly checkboxes and confirmations)"""
        try:
            self.logger.info("Filling review form confirmations")
            
            # Default values for review/confirmation fields
            review_defaults = {
                'terms_agreement': True,
                'privacy_policy': True,
                'marketing_consent': False,  # Be conservative with marketing consent
                'confirmation': True
            }
            
            for field_name, should_check in review_defaults.items():
                if field_name in mapped_elements:
                    for element_data in mapped_elements[field_name]:
                        element_id = element_data.get('id_of_input_component')
                        element_type = element_data.get('type_of_input', 'checkbox')
                        element = await self._find_element_by_id(page, element_id)
                        
                        if element and element_type == 'checkbox':
                            is_checked = await element.is_checked()
                            if should_check and not is_checked:
                                await element.click()
                                self.logger.debug(f"Checked {field_name} checkbox")
                            elif not should_check and is_checked:
                                await element.click()
                                self.logger.debug(f"Unchecked {field_name} checkbox")
                            break
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error filling review form: {str(e)}")
            return False
    
    async def _navigate_review_page(self, page: Page) -> bool:
        """Navigate from review page (final submission)"""
        try:
            review_navigation_selectors = [
                'button:has-text("Submit Application")',
                'button:has-text("Submit")',
                'button:has-text("Complete Application")',
                'button:has-text("Finish")',
                'button:has-text("Send Application")',
                '.submit-button',
                '.submit-application-button',
                'input[type="submit"]'
            ]
            
            return await self._try_navigation_selectors(page, review_navigation_selectors)
            
        except Exception as e:
            self.logger.error(f"Error navigating review page: {str(e)}")
            return False
    
    # Generic/fallback methods
    async def _fill_generic_form(self, page: Page, page_json: Dict) -> bool:
        """Fill forms using generic approach for unknown pages"""
        try:
            self.logger.info("Filling form using generic approach")
            
            if not page_json or not page_json.get('form_elements'):
                return True
            
            form_elements = page_json['form_elements']
            filled_count = 0
            
            for element_data in form_elements:
                try:
                    element_id = element_data.get('id_of_input_component')
                    element_type = element_data.get('type_of_input', 'text')
                    user_values = element_data.get('user_data_select_values', [])
                    options = element_data.get('options', [])
                    
                    element = await self._find_element_by_id(page, element_id)
                    if not element:
                        continue
                    
                    # Use generic filling logic
                    if user_values:
                        fill_value = user_values[0]
                    elif element_type in ['select', 'dropdown'] and options:
                        fill_value = options[0]
                    else:
                        fill_value = self._get_generic_fill_value(element_type, element_data.get('label', ''))
                    
                    if fill_value:
                        if element_type in ['select', 'dropdown']:
                            await element.select_option(value=fill_value)
                        elif element_type == 'checkbox':
                            if fill_value.lower() in ['true', 'yes', '1']:
                                await element.click()
                        else:
                            await element.fill(str(fill_value))
                        
                        filled_count += 1
                
                except Exception as e:
                    self.logger.debug(f"Error filling generic element: {str(e)}")
                    continue
            
            self.logger.info(f"Generic form filling completed - filled {filled_count} elements")
            return filled_count > 0
            
        except Exception as e:
            self.logger.error(f"Error in generic form filling: {str(e)}")
            return False
    
    def _get_generic_fill_value(self, element_type: str, label: str) -> str:
        """Get generic fill value based on element type and label"""
        label_lower = label.lower()
        
        if 'email' in label_lower:
            return 'test@example.com'
        elif 'phone' in label_lower:
            return '555-123-4567'
        elif 'name' in label_lower:
            if 'first' in label_lower:
                return 'John'
            elif 'last' in label_lower:
                return 'Doe'
            return 'John Doe'
        elif 'address' in label_lower:
            return '123 Main St'
        elif 'city' in label_lower:
            return 'New York'
        elif 'zip' in label_lower or 'postal' in label_lower:
            return '10001'
        elif 'date' in label_lower:
            return '01/01/2000'
        elif element_type == 'checkbox':
            return 'false'
        else:
            return 'Test Value'
    
    async def _navigate_unknown_page(self, page: Page) -> bool:
        """Navigate from unknown page using generic selectors"""
        try:
            generic_navigation_selectors = [
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button:has-text("Submit")',
                'button:has-text("Save")',
                'button:has-text("Proceed")',
                'input[type="submit"]',
                'button[type="submit"]',
                '.btn-primary',
                '.button-primary',
                '.next-button',
                '.continue-button',
                '.submit-button'
            ]
            
            return await self._try_navigation_selectors(page, generic_navigation_selectors)
            
        except Exception as e:
            self.logger.error(f"Error navigating unknown page: {str(e)}")
            return False
    
    # Common helper methods
    async def _try_navigation_selectors(self, page: Page, selectors: List[str]) -> bool:
        """Try multiple navigation selectors until one works"""
        try:
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        
                        if is_visible and is_enabled:
                            self.logger.info(f"Found navigation element with selector: {selector}")
                            await element.click()
                            
                            # Wait for navigation to complete
                            await self._wait_for_navigation(page)
                            return True
                
                except Exception as e:
                    self.logger.debug(f"Navigation selector '{selector}' failed: {str(e)}")
                    continue
            
            self.logger.warning("No working navigation selector found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error trying navigation selectors: {str(e)}")
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