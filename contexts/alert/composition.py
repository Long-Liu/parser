"""Alert bounded-context composition."""

from contexts.alert.application.alert_app_service import AlertApplicationService
from contexts.alert.domain.repositories import AlertMetricProvider, AlertPushDispatcher, AlertRepository
from contexts.shared.application.transaction import TransactionManager


def build_alert_service(
    repository: AlertRepository,
    metrics: AlertMetricProvider,
    dispatcher: AlertPushDispatcher,
    transactions: TransactionManager,
) -> AlertApplicationService:
    return AlertApplicationService(repository, metrics, dispatcher, transactions)
