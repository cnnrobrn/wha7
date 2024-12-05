
# scripts/azure/monitoring.py
"""Azure monitoring and alerts setup script."""

from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient
import os

def setup_monitoring(environment: str):
    """Set up Azure monitoring and alerts."""
    try:
        # Initialize credentials
        credential = DefaultAzureCredential()
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        
        # Initialize monitor client
        monitor_client = MonitorManagementClient(credential, subscription_id)
        
        resource_group = f"wha7-{environment}-rg"
        app_name = f"wha7-{environment}-app"
        
        # Set up metrics alerts
        alerts = [
            {
                "name": "high-cpu-alert",
                "description": "Alert when CPU usage is high",
                "metric_name": "CpuPercentage",
                "threshold": 80,
                "window_size": "PT5M"
            },
            {
                "name": "response-time-alert",
                "description": "Alert when response time is high",
                "metric_name": "HttpResponseTime",
                "threshold": 5,
                "window_size": "PT5M"
            },
            {
                "name": "error-rate-alert",
                "description": "Alert when error rate is high",
                "metric_name": "Http5xx",
                "threshold": 10,
                "window_size": "PT5M"
            }
        ]
        
        # Create alerts
        for alert in alerts:
            monitor_client.metric_alerts.create_or_update(
                resource_group,
                alert["name"],
                {
                    "location": "global",
                    "description": alert["description"],
                    "severity": 2,
                    "enabled": True,
                    "scopes": [
                        f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{app_name}"
                    ],
                    "evaluation_frequency": "PT1M",
                    "window_size": alert["window_size"],
                    "criteria": {
                        "odata.type": "Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria",
                        "all_of": [
                            {
                                "criterion_type": "StaticThresholdCriterion",
                                "metric_name": alert["metric_name"],
                                "metric_namespace": "Microsoft.Web/sites",
                                "operator": "GreaterThan",
                                "threshold": alert["threshold"],
                                "time_aggregation": "Average"
                            }
                        ]
                    },
                    "actions": [
                        {
                            "action_group_id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/microsoft.insights/actionGroups/emailAlert"
                        }
                    ]
                }
            )
        
        print(f"Monitoring setup completed for {environment}")
        
    except Exception as e:
        print(f"Monitoring setup failed: {str(e)}")
        raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", choices=["dev", "staging", "prod"])
    args = parser.parse_args()
    setup_monitoring(args.env)