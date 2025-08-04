import sys
from datetime import datetime

class AutomationCompleteException(Exception):
    """Raised when automation should end due to reaching completion URL"""
    def __init__(self, message="Automation complete"):
        self.message = message
        self.success = True
        super().__init__(self.message)
        
    def display_completion_message(self):
        """Display a formatted completion message"""
        print("\n" + "="*80)
        print("🎉 Workday Application Automation Complete! 🎉")
        print(f"✨ Status: {'Success' if self.success else 'Failed'}")
        print(f"✨ Message: {self.message}")
        print("✨ Application process has been completed")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"✨ Completed at: {current_time}")
        print("="*80 + "\n")
        if self.success:
            sys.exit(0)
        else:
            sys.exit(1)
