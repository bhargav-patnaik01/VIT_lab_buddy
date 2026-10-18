"""Notifications: Amazon SNS on AWS, log output locally."""
import logging

from .config import get_settings

log = logging.getLogger("cad.notify")


def publish(subject: str, message: str) -> str:
    s = get_settings()
    if s.sns_topic_arn:
        import boto3

        boto3.client("sns").publish(TopicArn=s.sns_topic_arn, Subject=subject[:100], Message=message)
        return "sns"
    log.info("NOTIFY (local, SNS not configured): %s\n%s", subject, message)
    return "log"
