"""
Health monitoring and alerting system for Binance Portfolio Logger.

This module provides health check capabilities, portfolio value validation,
alerting mechanisms, and execution metrics collection for system monitoring.
"""

import json
import os
import statistics
import smtplib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

from ..models.data_models import PortfolioValue


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class Alert:
    """Alert message for critical failures."""
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }


@dataclass
class PortfolioValueHistory:
    """Historical portfolio value data for trend analysis."""
    timestamp: datetime
    value: float
    change_percent: Optional[float] = None
    change_absolute: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'change_percent': self.change_percent,
            'change_absolute': self.change_absolute
        }


class HealthMonitor:
    """
    Comprehensive health monitoring and alerting system.
    
    Provides health checks, portfolio value validation, alerting mechanisms,
    and execution metrics collection for system monitoring.
    """
    
    def __init__(self, 
                 data_dir: str = "/var/log/binance-portfolio",
                 history_file: str = "portfolio_history.json",
                 health_file: str = "health_status.json",
                 alerts_file: str = "alerts.json"):
        """
        Initialize the health monitor.
        
        Args:
            data_dir: Directory for storing monitoring data
            history_file: Filename for portfolio value history
            health_file: Filename for health status data
            alerts_file: Filename for alerts data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.history_file = self.data_dir / history_file
        self.health_file = self.data_dir / health_file
        self.alerts_file = self.data_dir / alerts_file
        
        # Configuration from environment variables
        self.portfolio_change_threshold = float(os.getenv('PORTFOLIO_CHANGE_THRESHOLD', '20.0'))  # 20%
        self.min_portfolio_value = float(os.getenv('MIN_PORTFOLIO_VALUE', '0.01'))  # $0.01 USDT
        self.max_execution_time = int(os.getenv('MAX_EXECUTION_TIME', '60'))  # 60 seconds
        self.history_retention_days = int(os.getenv('HISTORY_RETENTION_DAYS', '30'))  # 30 days
        
        # Email configuration for alerts
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email_to = os.getenv('ALERT_EMAIL_TO')
        self.alert_email_from = os.getenv('ALERT_EMAIL_FROM', self.smtp_username)
        
        self.email_enabled = EMAIL_AVAILABLE and all([
            self.smtp_server, self.smtp_username, self.smtp_password, self.alert_email_to
        ])
    
    def run_health_checks(self) -> Dict[str, Any]:
        """
        Run comprehensive health checks on the system.
        
        Returns:
            Dict containing health check results and overall status
        """
        health_checks = []
        
        # Check 1: Log file accessibility
        health_checks.append(self._check_log_files())
        
        # Check 2: Configuration files
        health_checks.append(self._check_configuration_files())
        
        # Check 3: Recent execution status
        health_checks.append(self._check_recent_execution())
        
        # Check 4: Portfolio value trends
        health_checks.append(self._check_portfolio_trends())
        
        # Check 5: System resources
        health_checks.append(self._check_system_resources())
        
        # Check 6: API connectivity (optional)
        if os.getenv('HEALTH_CHECK_API', 'false').lower() == 'true':
            health_checks.append(self._check_api_connectivity())
        
        # Determine overall health status
        overall_status = self._determine_overall_status(health_checks)
        
        health_report = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status.value,
            'checks': [check.to_dict() for check in health_checks],
            'summary': self._generate_health_summary(health_checks)
        }
        
        # Save health status
        self._save_health_status(health_report)
        
        return health_report
    
    def validate_portfolio_value(self, portfolio_value: PortfolioValue) -> Tuple[bool, List[str]]:
        """
        Validate portfolio value for unusual changes.
        
        Args:
            portfolio_value: Current portfolio value to validate
            
        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []
        is_valid = True
        
        try:
            # Load historical data
            history = self._load_portfolio_history()
            
            # Add current value to history
            current_entry = PortfolioValueHistory(
                timestamp=portfolio_value.timestamp,
                value=portfolio_value.total_usdt
            )
            
            if history:
                # Calculate change from last value
                last_entry = history[-1]
                time_diff = (current_entry.timestamp - last_entry.timestamp).total_seconds()
                
                if time_diff > 0:  # Ensure we have a time difference
                    current_entry.change_absolute = current_entry.value - last_entry.value
                    
                    if last_entry.value > 0:
                        current_entry.change_percent = (current_entry.change_absolute / last_entry.value) * 100
                    else:
                        current_entry.change_percent = 0.0
                    
                    # Check for unusual changes
                    if abs(current_entry.change_percent) > self.portfolio_change_threshold:
                        warning_msg = (
                            f"Large portfolio change detected: "
                            f"{current_entry.change_percent:.2f}% "
                            f"(${current_entry.change_absolute:.2f} USDT) "
                            f"from ${last_entry.value:.2f} to ${current_entry.value:.2f}"
                        )
                        warnings.append(warning_msg)
                        
                        # Create alert for large changes
                        alert = Alert(
                            level=AlertLevel.WARNING,
                            title="Large Portfolio Value Change",
                            message=warning_msg,
                            details={
                                'previous_value': last_entry.value,
                                'current_value': current_entry.value,
                                'change_percent': current_entry.change_percent,
                                'change_absolute': current_entry.change_absolute,
                                'threshold': self.portfolio_change_threshold
                            }
                        )
                        self._send_alert(alert)
                    
                    # Check for suspicious zero values
                    if current_entry.value == 0.0 and last_entry.value > self.min_portfolio_value:
                        warning_msg = (
                            f"Portfolio value dropped to zero from ${last_entry.value:.2f}. "
                            "This may indicate an API issue or configuration problem."
                        )
                        warnings.append(warning_msg)
                        is_valid = False
                        
                        alert = Alert(
                            level=AlertLevel.CRITICAL,
                            title="Portfolio Value Dropped to Zero",
                            message=warning_msg,
                            details={
                                'previous_value': last_entry.value,
                                'current_value': current_entry.value
                            }
                        )
                        self._send_alert(alert)
            
            # Add to history and save
            history.append(current_entry)
            self._save_portfolio_history(history)
            
            # Check for trend analysis (if we have enough data)
            if len(history) >= 7:  # At least a week of data
                trend_warnings = self._analyze_portfolio_trends(history)
                warnings.extend(trend_warnings)
            
        except Exception as e:
            warning_msg = f"Error validating portfolio value: {str(e)}"
            warnings.append(warning_msg)
            is_valid = False
        
        return is_valid, warnings
    
    def collect_execution_metrics(self, execution_metrics: Dict[str, Any]) -> None:
        """
        Collect and store execution metrics for monitoring.
        
        Args:
            execution_metrics: Metrics from the execution
        """
        try:
            # Add timestamp if not present
            if 'timestamp' not in execution_metrics:
                execution_metrics['timestamp'] = datetime.now().isoformat()
            
            # Load existing metrics
            metrics_file = self.data_dir / "execution_metrics.json"
            metrics_history = []
            
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    metrics_history = json.load(f)
            
            # Add current metrics
            metrics_history.append(execution_metrics)
            
            # Keep only recent metrics (last 100 executions or 30 days)
            cutoff_date = datetime.now() - timedelta(days=self.history_retention_days)
            metrics_history = [
                m for m in metrics_history[-100:]  # Keep last 100
                if datetime.fromisoformat(m['timestamp']) > cutoff_date
            ]
            
            # Save updated metrics
            with open(metrics_file, 'w') as f:
                json.dump(metrics_history, f, indent=2)
            
            # Check for performance issues
            self._check_execution_performance(execution_metrics)
            
        except Exception as e:
            # Log error but don't fail the main execution
            print(f"Warning: Failed to collect execution metrics: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status from saved data.
        
        Returns:
            Dict containing current health status
        """
        try:
            if self.health_file.exists():
                with open(self.health_file, 'r') as f:
                    return json.load(f)
            else:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'overall_status': HealthStatus.UNKNOWN.value,
                    'message': 'No health data available'
                }
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': HealthStatus.CRITICAL.value,
                'message': f'Error reading health status: {e}'
            }
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get recent alerts from the specified time period.
        
        Args:
            hours: Number of hours to look back for alerts
            
        Returns:
            List of recent alerts
        """
        try:
            if not self.alerts_file.exists():
                return []
            
            with open(self.alerts_file, 'r') as f:
                all_alerts = json.load(f)
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            recent_alerts = [
                alert for alert in all_alerts
                if datetime.fromisoformat(alert['timestamp']) > cutoff_time
            ]
            
            return recent_alerts
            
        except Exception as e:
            return [{
                'level': AlertLevel.CRITICAL.value,
                'title': 'Error Reading Alerts',
                'message': f'Failed to read alerts file: {e}',
                'timestamp': datetime.now().isoformat()
            }]
    
    def _check_log_files(self) -> HealthCheckResult:
        """Check accessibility and recent activity of log files."""
        try:
            log_files = [
                "/var/log/binance-portfolio/portfolio.log",
                "/var/log/binance-portfolio/portfolio_errors.log",
                "/var/log/binance-portfolio/portfolio_metrics.log"
            ]
            
            issues = []
            for log_file in log_files:
                log_path = Path(log_file)
                if not log_path.exists():
                    issues.append(f"Log file missing: {log_file}")
                elif not os.access(log_path, os.R_OK):
                    issues.append(f"Log file not readable: {log_file}")
            
            if issues:
                return HealthCheckResult(
                    name="Log Files",
                    status=HealthStatus.WARNING,
                    message=f"Log file issues: {'; '.join(issues)}",
                    details={'issues': issues}
                )
            else:
                return HealthCheckResult(
                    name="Log Files",
                    status=HealthStatus.HEALTHY,
                    message="All log files accessible"
                )
                
        except Exception as e:
            return HealthCheckResult(
                name="Log Files",
                status=HealthStatus.CRITICAL,
                message=f"Error checking log files: {e}"
            )
    
    def _check_configuration_files(self) -> HealthCheckResult:
        """Check configuration files and environment variables."""
        try:
            required_env_vars = [
                'BINANCE_API_KEY',
                'BINANCE_API_SECRET',
                'GOOGLE_SERVICE_ACCOUNT_PATH',
                'GOOGLE_SPREADSHEET_ID'
            ]
            
            missing_vars = []
            for var in required_env_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            # Check Google service account file
            service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
            if service_account_path and not Path(service_account_path).exists():
                missing_vars.append(f"File not found: {service_account_path}")
            
            if missing_vars:
                return HealthCheckResult(
                    name="Configuration",
                    status=HealthStatus.CRITICAL,
                    message=f"Missing configuration: {', '.join(missing_vars)}",
                    details={'missing': missing_vars}
                )
            else:
                return HealthCheckResult(
                    name="Configuration",
                    status=HealthStatus.HEALTHY,
                    message="All required configuration present"
                )
                
        except Exception as e:
            return HealthCheckResult(
                name="Configuration",
                status=HealthStatus.CRITICAL,
                message=f"Error checking configuration: {e}"
            )
    
    def _check_recent_execution(self) -> HealthCheckResult:
        """Check recent execution status from logs."""
        try:
            log_file = Path("/var/log/binance-portfolio/portfolio.log")
            if not log_file.exists():
                return HealthCheckResult(
                    name="Recent Execution",
                    status=HealthStatus.WARNING,
                    message="No log file found to check recent execution"
                )
            
            # Check last 50 lines for recent execution
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-50:] if len(lines) > 50 else lines
            
            # Look for recent success or failure
            recent_success = False
            recent_failure = False
            last_execution_time = None
            
            for line in reversed(recent_lines):
                if 'Portfolio logging completed successfully' in line:
                    recent_success = True
                    # Extract timestamp from log line
                    try:
                        timestamp_str = line.split(' - ')[0]
                        last_execution_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                    break
                elif 'Portfolio logging execution failed' in line:
                    recent_failure = True
                    try:
                        timestamp_str = line.split(' - ')[0]
                        last_execution_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                    break
            
            if recent_success:
                time_since = (datetime.now() - last_execution_time).total_seconds() if last_execution_time else None
                if time_since and time_since < 86400:  # Less than 24 hours
                    return HealthCheckResult(
                        name="Recent Execution",
                        status=HealthStatus.HEALTHY,
                        message=f"Recent successful execution {time_since/3600:.1f} hours ago",
                        details={'last_execution': last_execution_time.isoformat() if last_execution_time else None}
                    )
                else:
                    return HealthCheckResult(
                        name="Recent Execution",
                        status=HealthStatus.WARNING,
                        message="No recent successful execution in last 24 hours",
                        details={'last_execution': last_execution_time.isoformat() if last_execution_time else None}
                    )
            elif recent_failure:
                return HealthCheckResult(
                    name="Recent Execution",
                    status=HealthStatus.CRITICAL,
                    message="Recent execution failed",
                    details={'last_execution': last_execution_time.isoformat() if last_execution_time else None}
                )
            else:
                return HealthCheckResult(
                    name="Recent Execution",
                    status=HealthStatus.UNKNOWN,
                    message="No recent execution information found"
                )
                
        except Exception as e:
            return HealthCheckResult(
                name="Recent Execution",
                status=HealthStatus.CRITICAL,
                message=f"Error checking recent execution: {e}"
            )
    
    def _check_portfolio_trends(self) -> HealthCheckResult:
        """Check portfolio value trends for anomalies."""
        try:
            history = self._load_portfolio_history()
            
            if len(history) < 2:
                return HealthCheckResult(
                    name="Portfolio Trends",
                    status=HealthStatus.UNKNOWN,
                    message="Insufficient historical data for trend analysis"
                )
            
            # Get recent values (last 7 days)
            recent_cutoff = datetime.now() - timedelta(days=7)
            recent_values = [
                h.value for h in history
                if h.timestamp > recent_cutoff
            ]
            
            if len(recent_values) < 2:
                return HealthCheckResult(
                    name="Portfolio Trends",
                    status=HealthStatus.WARNING,
                    message="Limited recent data for trend analysis"
                )
            
            # Calculate trend statistics
            avg_value = statistics.mean(recent_values)
            std_dev = statistics.stdev(recent_values) if len(recent_values) > 1 else 0
            min_value = min(recent_values)
            max_value = max(recent_values)
            
            # Check for concerning trends
            if std_dev > avg_value * 0.5:  # High volatility
                return HealthCheckResult(
                    name="Portfolio Trends",
                    status=HealthStatus.WARNING,
                    message=f"High portfolio volatility detected (std dev: {std_dev:.2f})",
                    details={
                        'avg_value': avg_value,
                        'std_dev': std_dev,
                        'min_value': min_value,
                        'max_value': max_value,
                        'data_points': len(recent_values)
                    }
                )
            else:
                return HealthCheckResult(
                    name="Portfolio Trends",
                    status=HealthStatus.HEALTHY,
                    message=f"Portfolio trends normal (avg: ${avg_value:.2f})",
                    details={
                        'avg_value': avg_value,
                        'std_dev': std_dev,
                        'min_value': min_value,
                        'max_value': max_value,
                        'data_points': len(recent_values)
                    }
                )
                
        except Exception as e:
            return HealthCheckResult(
                name="Portfolio Trends",
                status=HealthStatus.CRITICAL,
                message=f"Error analyzing portfolio trends: {e}"
            )
    
    def _check_system_resources(self) -> HealthCheckResult:
        """Check system resources like disk space."""
        try:
            import shutil
            
            # Check disk space for log directory
            log_dir = Path("/var/log/binance-portfolio")
            if log_dir.exists():
                total, used, free = shutil.disk_usage(log_dir)
                free_percent = (free / total) * 100
                
                if free_percent < 5:  # Less than 5% free
                    return HealthCheckResult(
                        name="System Resources",
                        status=HealthStatus.CRITICAL,
                        message=f"Low disk space: {free_percent:.1f}% free",
                        details={
                            'total_gb': total / (1024**3),
                            'used_gb': used / (1024**3),
                            'free_gb': free / (1024**3),
                            'free_percent': free_percent
                        }
                    )
                elif free_percent < 15:  # Less than 15% free
                    return HealthCheckResult(
                        name="System Resources",
                        status=HealthStatus.WARNING,
                        message=f"Disk space getting low: {free_percent:.1f}% free",
                        details={
                            'total_gb': total / (1024**3),
                            'used_gb': used / (1024**3),
                            'free_gb': free / (1024**3),
                            'free_percent': free_percent
                        }
                    )
                else:
                    return HealthCheckResult(
                        name="System Resources",
                        status=HealthStatus.HEALTHY,
                        message=f"Disk space adequate: {free_percent:.1f}% free",
                        details={
                            'total_gb': total / (1024**3),
                            'free_gb': free / (1024**3),
                            'free_percent': free_percent
                        }
                    )
            else:
                return HealthCheckResult(
                    name="System Resources",
                    status=HealthStatus.WARNING,
                    message="Log directory does not exist"
                )
                
        except Exception as e:
            return HealthCheckResult(
                name="System Resources",
                status=HealthStatus.CRITICAL,
                message=f"Error checking system resources: {e}"
            )
    
    def _check_api_connectivity(self) -> HealthCheckResult:
        """Check API connectivity (optional, can be slow)."""
        try:
            import requests
            
            # Test basic internet connectivity
            response = requests.get('https://api.binance.com/api/v3/ping', timeout=10)
            if response.status_code == 200:
                return HealthCheckResult(
                    name="API Connectivity",
                    status=HealthStatus.HEALTHY,
                    message="Binance API connectivity confirmed"
                )
            else:
                return HealthCheckResult(
                    name="API Connectivity",
                    status=HealthStatus.WARNING,
                    message=f"Binance API returned status {response.status_code}"
                )
                
        except Exception as e:
            return HealthCheckResult(
                name="API Connectivity",
                status=HealthStatus.CRITICAL,
                message=f"API connectivity test failed: {e}"
            )
    
    def _determine_overall_status(self, health_checks: List[HealthCheckResult]) -> HealthStatus:
        """Determine overall health status from individual checks."""
        if any(check.status == HealthStatus.CRITICAL for check in health_checks):
            return HealthStatus.CRITICAL
        elif any(check.status == HealthStatus.WARNING for check in health_checks):
            return HealthStatus.WARNING
        elif any(check.status == HealthStatus.UNKNOWN for check in health_checks):
            return HealthStatus.WARNING  # Treat unknown as warning
        else:
            return HealthStatus.HEALTHY
    
    def _generate_health_summary(self, health_checks: List[HealthCheckResult]) -> Dict[str, Any]:
        """Generate summary statistics from health checks."""
        status_counts = {}
        for status in HealthStatus:
            status_counts[status.value] = sum(1 for check in health_checks if check.status == status)
        
        return {
            'total_checks': len(health_checks),
            'status_counts': status_counts,
            'critical_issues': [
                check.name for check in health_checks 
                if check.status == HealthStatus.CRITICAL
            ],
            'warnings': [
                check.name for check in health_checks 
                if check.status == HealthStatus.WARNING
            ]
        }
    
    def _load_portfolio_history(self) -> List[PortfolioValueHistory]:
        """Load portfolio value history from file."""
        try:
            if not self.history_file.exists():
                return []
            
            with open(self.history_file, 'r') as f:
                data = json.load(f)
            
            history = []
            for item in data:
                history.append(PortfolioValueHistory(
                    timestamp=datetime.fromisoformat(item['timestamp']),
                    value=item['value'],
                    change_percent=item.get('change_percent'),
                    change_absolute=item.get('change_absolute')
                ))
            
            # Clean old entries
            cutoff_date = datetime.now() - timedelta(days=self.history_retention_days)
            history = [h for h in history if h.timestamp > cutoff_date]
            
            return history
            
        except Exception as e:
            print(f"Warning: Failed to load portfolio history: {e}")
            return []
    
    def _save_portfolio_history(self, history: List[PortfolioValueHistory]) -> None:
        """Save portfolio value history to file."""
        try:
            data = [h.to_dict() for h in history]
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save portfolio history: {e}")
    
    def _save_health_status(self, health_report: Dict[str, Any]) -> None:
        """Save health status to file."""
        try:
            with open(self.health_file, 'w') as f:
                json.dump(health_report, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save health status: {e}")
    
    def _analyze_portfolio_trends(self, history: List[PortfolioValueHistory]) -> List[str]:
        """Analyze portfolio trends for warnings."""
        warnings = []
        
        try:
            if len(history) < 7:
                return warnings
            
            # Get last 7 days of data
            recent_history = history[-7:]
            values = [h.value for h in recent_history]
            
            # Check for consistent decline
            declining_days = 0
            for i in range(1, len(values)):
                if values[i] < values[i-1]:
                    declining_days += 1
            
            if declining_days >= 5:  # 5 out of 6 days declining
                total_decline = ((values[0] - values[-1]) / values[0]) * 100
                warnings.append(
                    f"Portfolio has been declining for {declining_days} consecutive days "
                    f"(total decline: {total_decline:.2f}%)"
                )
            
            # Check for unusual patterns (all zeros, identical values)
            if all(v == 0 for v in values[-3:]):  # Last 3 values are zero
                warnings.append("Portfolio value has been zero for multiple days")
            
            unique_values = set(values[-5:])  # Last 5 values
            if len(unique_values) == 1 and len(values) >= 5:
                warnings.append("Portfolio value has been identical for multiple days")
            
        except Exception as e:
            warnings.append(f"Error analyzing portfolio trends: {e}")
        
        return warnings
    
    def _check_execution_performance(self, metrics: Dict[str, Any]) -> None:
        """Check execution performance and create alerts if needed."""
        try:
            execution_time = metrics.get('execution_duration_seconds', 0)
            
            if execution_time > self.max_execution_time:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    title="Slow Execution Performance",
                    message=f"Execution took {execution_time:.2f}s (threshold: {self.max_execution_time}s)",
                    details={
                        'execution_time': execution_time,
                        'threshold': self.max_execution_time,
                        'metrics': metrics
                    }
                )
                self._send_alert(alert)
            
            # Check for high error rates
            errors_count = metrics.get('errors_count', 0)
            if errors_count > 0:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    title="Execution Errors Detected",
                    message=f"Execution completed with {errors_count} errors",
                    details={
                        'errors_count': errors_count,
                        'metrics': metrics
                    }
                )
                self._send_alert(alert)
                
        except Exception as e:
            print(f"Warning: Failed to check execution performance: {e}")
    
    def _send_alert(self, alert: Alert) -> None:
        """Send alert via configured channels."""
        try:
            # Save alert to file
            self._save_alert(alert)
            
            # Send email if configured
            if self.email_enabled:
                self._send_email_alert(alert)
            
        except Exception as e:
            print(f"Warning: Failed to send alert: {e}")
    
    def _save_alert(self, alert: Alert) -> None:
        """Save alert to alerts file."""
        try:
            alerts = []
            if self.alerts_file.exists():
                with open(self.alerts_file, 'r') as f:
                    alerts = json.load(f)
            
            alerts.append(alert.to_dict())
            
            # Keep only recent alerts (last 1000 or 30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            alerts = [
                a for a in alerts[-1000:]  # Keep last 1000
                if datetime.fromisoformat(a['timestamp']) > cutoff_date
            ]
            
            with open(self.alerts_file, 'w') as f:
                json.dump(alerts, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Failed to save alert: {e}")
    
    def _send_email_alert(self, alert: Alert) -> None:
        """Send alert via email."""
        try:
            if not self.email_enabled or not EMAIL_AVAILABLE:
                return
            
            # Create email message
            msg = MimeMultipart()
            msg['From'] = self.alert_email_from
            msg['To'] = self.alert_email_to
            msg['Subject'] = f"[{alert.level.value.upper()}] Binance Portfolio Logger: {alert.title}"
            
            # Email body
            body = f"""
Alert Level: {alert.level.value.upper()}
Title: {alert.title}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Message:
{alert.message}

Details:
{json.dumps(alert.details, indent=2)}

---
This alert was generated by the Binance Portfolio Logger monitoring system.
            """.strip()
            
            msg.attach(MimeText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
        except Exception as e:
            print(f"Warning: Failed to send email alert: {e}")