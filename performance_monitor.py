#!/usr/bin/env python3
"""
Performance Monitor for Workday Page Automation
Task 13: Add performance monitoring and optimization

This module provides comprehensive performance monitoring including:
- Timing measurements for page processing operations
- Memory usage monitoring during automation runs
- Performance logging and metrics collection
- Optimized waiting strategies and resource management

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import os
import time
import psutil
import logging
import json
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable
from contextlib import asynccontextmanager, contextmanager
from functools import wraps
import threading
from collections import defaultdict, deque
import gc

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation"""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    memory_before: float
    memory_after: float
    memory_delta: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PagePerformanceData:
    """Performance data for a specific page"""
    page_name: str
    page_index: int
    total_duration: float
    form_extraction_time: float
    form_filling_time: float
    navigation_time: float
    memory_peak: float
    memory_average: float
    cpu_peak: float
    cpu_average: float
    retry_count: int
    success: bool
    error_count: int
    timestamp: float

@dataclass
class AutomationPerformanceReport:
    """Complete performance report for automation run"""
    automation_id: str
    start_time: float
    end_time: float
    total_duration: float
    pages_processed: int
    pages_successful: int
    pages_failed: int
    total_memory_peak: float
    total_memory_average: float
    total_cpu_peak: float
    total_cpu_average: float
    page_performance_data: List[PagePerformanceData]
    operation_metrics: List[PerformanceMetrics]
    optimization_suggestions: List[str]
    performance_score: float
    timestamp: float

class PerformanceMonitor:
    """
    Comprehensive performance monitoring system for Workday automation
    Requirements: 6.1, 6.2, 6.3, 6.4
    """
    
    def __init__(self, enable_monitoring: bool = True, log_interval: int = 30):
        self.enable_monitoring = enable_monitoring
        self.log_interval = log_interval  # seconds
        
        # Performance tracking
        self.operation_metrics: List[PerformanceMetrics] = []
        self.page_performance_data: List[PagePerformanceData] = []
        self.current_page_data: Optional[PagePerformanceData] = None
        
        # Memory and CPU monitoring
        self.memory_samples: deque = deque(maxlen=1000)
        self.cpu_samples: deque = deque(maxlen=1000)
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        
        # Timing tracking
        self.automation_start_time: Optional[float] = None
        self.automation_end_time: Optional[float] = None
        self.page_start_times: Dict[int, float] = {}
        self.operation_start_times: Dict[str, float] = {}
        
        # Performance optimization
        self.wait_strategies = {
            'aggressive': {'page_load': 5000, 'element_wait': 3000, 'navigation': 2000},
            'balanced': {'page_load': 10000, 'element_wait': 5000, 'navigation': 3000},
            'conservative': {'page_load': 15000, 'element_wait': 8000, 'navigation': 5000}
        }
        self.current_strategy = 'balanced'
        
        # Resource management
        self.gc_threshold = 100  # MB
        self.last_gc_time = 0
        self.gc_interval = 60  # seconds
        
        logger.info("Performance Monitor initialized")
    
    def start_automation_monitoring(self, automation_id: str):
        """Start monitoring for a new automation run"""
        if not self.enable_monitoring:
            return
        
        self.automation_start_time = time.time()
        self.operation_metrics.clear()
        self.page_performance_data.clear()
        self.memory_samples.clear()
        self.cpu_samples.clear()
        
        # Start background monitoring
        self._start_background_monitoring()
        
        logger.info(f"Performance monitoring started for automation: {automation_id}")
    
    def stop_automation_monitoring(self):
        """Stop monitoring and generate final report"""
        if not self.enable_monitoring:
            return
        
        self.automation_end_time = time.time()
        self._stop_background_monitoring()
        
        logger.info("Performance monitoring stopped")
    
    def _start_background_monitoring(self):
        """Start background thread for continuous memory and CPU monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitor_resources, daemon=True)
        self.monitoring_thread.start()
    
    def _stop_background_monitoring(self):
        """Stop background monitoring thread"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
    
    def _monitor_resources(self):
        """Background thread for monitoring system resources"""
        while self.monitoring_active:
            try:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent()
                
                self.memory_samples.append(memory_mb)
                self.cpu_samples.append(cpu_percent)
                
                # Check if garbage collection is needed
                if memory_mb > self.gc_threshold and time.time() - self.last_gc_time > self.gc_interval:
                    self._trigger_garbage_collection()
                
                time.sleep(1)  # Sample every second
                
            except Exception as e:
                logger.warning(f"Error in resource monitoring: {e}")
                time.sleep(5)
    
    def _trigger_garbage_collection(self):
        """Trigger garbage collection when memory usage is high"""
        try:
            collected = gc.collect()
            self.last_gc_time = time.time()
            logger.debug(f"Garbage collection triggered, collected {collected} objects")
        except Exception as e:
            logger.warning(f"Error during garbage collection: {e}")
    
    @contextmanager
    def measure_operation(self, operation_name: str, additional_data: Dict[str, Any] = None):
        """Context manager for measuring operation performance"""
        if not self.enable_monitoring:
            yield
            return
        
        start_time = time.time()
        memory_before = self._get_current_memory_usage()
        cpu_before = self._get_current_cpu_usage()
        
        try:
            yield
            success = True
            error_message = None
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            memory_after = self._get_current_memory_usage()
            cpu_after = self._get_current_cpu_usage()
            
            metric = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_delta=memory_after - memory_before,
                cpu_percent=(cpu_before + cpu_after) / 2,
                success=success,
                error_message=error_message,
                additional_data=additional_data or {}
            )
            
            self.operation_metrics.append(metric)
            
            # Log performance if operation takes significant time
            if metric.duration > 5.0:  # Log operations taking more than 5 seconds
                logger.info(f"Performance: {operation_name} took {metric.duration:.2f}s, "
                          f"memory delta: {metric.memory_delta:.2f}MB")
    
    @asynccontextmanager
    async def measure_async_operation(self, operation_name: str, additional_data: Dict[str, Any] = None):
        """Async context manager for measuring operation performance"""
        if not self.enable_monitoring:
            yield
            return
        
        start_time = time.time()
        memory_before = self._get_current_memory_usage()
        cpu_before = self._get_current_cpu_usage()
        
        try:
            yield
            success = True
            error_message = None
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            memory_after = self._get_current_memory_usage()
            cpu_after = self._get_current_cpu_usage()
            
            metric = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                memory_before=memory_before,
                memory_after=memory_after,
                memory_delta=memory_after - memory_before,
                cpu_percent=(cpu_before + cpu_after) / 2,
                success=success,
                error_message=error_message,
                additional_data=additional_data or {}
            )
            
            self.operation_metrics.append(metric)
            
            # Log performance if operation takes significant time
            if metric.duration > 5.0:  # Log operations taking more than 5 seconds
                logger.info(f"Performance: {operation_name} took {metric.duration:.2f}s, "
                          f"memory delta: {metric.memory_delta:.2f}MB")
    
    def start_page_monitoring(self, page_name: str, page_index: int):
        """Start monitoring for a specific page"""
        if not self.enable_monitoring:
            return
        
        self.current_page_data = PagePerformanceData(
            page_name=page_name,
            page_index=page_index,
            total_duration=0.0,
            form_extraction_time=0.0,
            form_filling_time=0.0,
            navigation_time=0.0,
            memory_peak=0.0,
            memory_average=0.0,
            cpu_peak=0.0,
            cpu_average=0.0,
            retry_count=0,
            success=False,
            error_count=0,
            timestamp=time.time()
        )
        
        self.page_start_times[page_index] = time.time()
        logger.debug(f"Started monitoring page: {page_name} (index: {page_index})")
    
    def end_page_monitoring(self, page_index: int, success: bool = True):
        """End monitoring for a specific page"""
        if not self.enable_monitoring or not self.current_page_data:
            return
        
        end_time = time.time()
        start_time = self.page_start_times.get(page_index, end_time)
        
        self.current_page_data.total_duration = end_time - start_time
        self.current_page_data.success = success
        self.current_page_data.memory_peak = max(self.memory_samples) if self.memory_samples else 0
        self.current_page_data.memory_average = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0
        self.current_page_data.cpu_peak = max(self.cpu_samples) if self.cpu_samples else 0
        self.current_page_data.cpu_average = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        
        self.page_performance_data.append(self.current_page_data)
        
        logger.info(f"Page performance: {self.current_page_data.page_name} "
                   f"took {self.current_page_data.total_duration:.2f}s, "
                   f"memory peak: {self.current_page_data.memory_peak:.2f}MB")
    
    def record_page_operation_time(self, operation: str, duration: float):
        """Record time for specific page operations"""
        if not self.enable_monitoring or not self.current_page_data:
            return
        
        if operation == 'form_extraction':
            self.current_page_data.form_extraction_time = duration
        elif operation == 'form_filling':
            self.current_page_data.form_filling_time = duration
        elif operation == 'navigation':
            self.current_page_data.navigation_time = duration
    
    def increment_retry_count(self):
        """Increment retry count for current page"""
        if self.current_page_data:
            self.current_page_data.retry_count += 1
    
    def increment_error_count(self):
        """Increment error count for current page"""
        if self.current_page_data:
            self.current_page_data.error_count += 1
    
    def _get_current_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def _get_current_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        try:
            process = psutil.Process()
            return process.cpu_percent()
        except Exception:
            return 0.0
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary"""
        if not self.operation_metrics:
            return {}
        
        total_operations = len(self.operation_metrics)
        successful_operations = sum(1 for m in self.operation_metrics if m.success)
        total_duration = sum(m.duration for m in self.operation_metrics)
        avg_duration = total_duration / total_operations if total_operations > 0 else 0
        
        memory_peak = max(self.memory_samples) if self.memory_samples else 0
        memory_average = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0
        cpu_peak = max(self.cpu_samples) if self.cpu_samples else 0
        cpu_average = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        
        return {
            'total_operations': total_operations,
            'successful_operations': successful_operations,
            'success_rate': (successful_operations / total_operations * 100) if total_operations > 0 else 0,
            'total_duration': total_duration,
            'average_duration': avg_duration,
            'memory_peak_mb': memory_peak,
            'memory_average_mb': memory_average,
            'cpu_peak_percent': cpu_peak,
            'cpu_average_percent': cpu_average
        }
    
    def generate_performance_report(self, automation_id: str) -> AutomationPerformanceReport:
        """Generate comprehensive performance report"""
        if not self.automation_start_time:
            raise ValueError("Automation monitoring not started")
        
        end_time = self.automation_end_time or time.time()
        total_duration = end_time - self.automation_start_time
        
        # Calculate performance score (0-100)
        performance_score = self._calculate_performance_score()
        
        # Generate optimization suggestions
        optimization_suggestions = self._generate_optimization_suggestions()
        
        report = AutomationPerformanceReport(
            automation_id=automation_id,
            start_time=self.automation_start_time,
            end_time=end_time,
            total_duration=total_duration,
            pages_processed=len(self.page_performance_data),
            pages_successful=sum(1 for p in self.page_performance_data if p.success),
            pages_failed=sum(1 for p in self.page_performance_data if not p.success),
            total_memory_peak=max(self.memory_samples) if self.memory_samples else 0,
            total_memory_average=sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0,
            total_cpu_peak=max(self.cpu_samples) if self.cpu_samples else 0,
            total_cpu_average=sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0,
            page_performance_data=self.page_performance_data.copy(),
            operation_metrics=self.operation_metrics.copy(),
            optimization_suggestions=optimization_suggestions,
            performance_score=performance_score,
            timestamp=time.time()
        )
        
        return report
    
    def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-100)"""
        if not self.operation_metrics:
            return 0.0
        
        # Factors for performance score
        success_rate = sum(1 for m in self.operation_metrics if m.success) / len(self.operation_metrics)
        avg_duration = sum(m.duration for m in self.operation_metrics) / len(self.operation_metrics)
        memory_efficiency = 1.0 - min(1.0, max(self.memory_samples) / 1000) if self.memory_samples else 1.0  # Penalize high memory usage
        
        # Weighted score
        score = (success_rate * 40) + (max(0, 1 - avg_duration / 60) * 30) + (memory_efficiency * 30)
        return min(100.0, max(0.0, score))
    
    def _generate_optimization_suggestions(self) -> List[str]:
        """Generate optimization suggestions based on performance data"""
        suggestions = []
        
        if not self.operation_metrics:
            return suggestions
        
        # Analyze operation durations
        slow_operations = [m for m in self.operation_metrics if m.duration > 10.0]
        if slow_operations:
            suggestions.append(f"Consider optimizing {len(slow_operations)} slow operations (>10s)")
        
        # Analyze memory usage
        if self.memory_samples:
            memory_peak = max(self.memory_samples)
            if memory_peak > 500:  # MB
                suggestions.append("High memory usage detected - consider implementing memory cleanup")
        
        # Analyze CPU usage
        if self.cpu_samples:
            cpu_peak = max(self.cpu_samples)
            if cpu_peak > 80:  # percent
                suggestions.append("High CPU usage detected - consider reducing concurrent operations")
        
        # Analyze retry patterns
        if self.page_performance_data:
            high_retry_pages = [p for p in self.page_performance_data if p.retry_count > 3]
            if high_retry_pages:
                suggestions.append(f"Pages with high retry counts detected - review error handling for {len(high_retry_pages)} pages")
        
        return suggestions
    
    def optimize_wait_strategy(self, current_performance: Dict[str, Any]) -> str:
        """Dynamically optimize wait strategy based on performance"""
        if not current_performance:
            return self.current_strategy
        
        avg_duration = current_performance.get('average_duration', 0)
        success_rate = current_performance.get('success_rate', 100)
        
        # Adjust strategy based on performance
        if success_rate < 80 and avg_duration < 5:
            # Low success rate, fast operations - be more conservative
            self.current_strategy = 'conservative'
        elif success_rate > 95 and avg_duration > 15:
            # High success rate, slow operations - be more aggressive
            self.current_strategy = 'aggressive'
        else:
            # Default to balanced
            self.current_strategy = 'balanced'
        
        logger.info(f"Wait strategy optimized to: {self.current_strategy}")
        return self.current_strategy
    
    def get_optimized_wait_times(self) -> Dict[str, int]:
        """Get optimized wait times based on current strategy"""
        return self.wait_strategies[self.current_strategy]
    
    def save_performance_report(self, report: AutomationPerformanceReport, file_path: str = None) -> bool:
        """Save performance report to JSON file"""
        try:
            if not file_path:
                timestamp = int(time.time())
                file_path = f"performance_report_{timestamp}.json"
            
            # Convert dataclass to dict for JSON serialization
            report_dict = asdict(report)
            
            with open(file_path, 'w') as f:
                json.dump(report_dict, f, indent=2, default=str)
            
            logger.info(f"Performance report saved to: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving performance report: {e}")
            return False
    
    def reset_monitoring(self):
        """Reset all monitoring data"""
        self.operation_metrics.clear()
        self.page_performance_data.clear()
        self.memory_samples.clear()
        self.cpu_samples.clear()
        self.page_start_times.clear()
        self.operation_start_times.clear()
        self.current_page_data = None
        self.automation_start_time = None
        self.automation_end_time = None
        
        logger.info("Performance monitoring data reset")


def performance_monitor(operation_name: str = None, additional_data: Dict[str, Any] = None):
    """
    Decorator for measuring function performance
    Usage: @performance_monitor("operation_name")
    """
    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Try to get monitor instance from args or kwargs
            monitor = None
            for arg in args:
                if hasattr(arg, 'performance_monitor'):
                    monitor = arg.performance_monitor
                    break
            
            if not monitor:
                for value in kwargs.values():
                    if hasattr(value, 'performance_monitor'):
                        monitor = value.performance_monitor
                        break
            
            if monitor:
                with monitor.measure_operation(operation_name or func.__name__, additional_data):
                    return func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Try to get monitor instance from args or kwargs
            monitor = None
            for arg in args:
                if hasattr(arg, 'performance_monitor'):
                    monitor = arg.performance_monitor
                    break
            
            if not monitor:
                for value in kwargs.values():
                    if hasattr(value, 'performance_monitor'):
                        monitor = value.performance_monitor
                        break
            
            if monitor:
                async with monitor.measure_async_operation(operation_name or func.__name__, additional_data):
                    return await func(*args, **kwargs)
            else:
                return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator 