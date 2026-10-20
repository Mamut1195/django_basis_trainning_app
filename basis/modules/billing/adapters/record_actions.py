from basis.bootstrap.billing import billing
from basis.modules.billing.adapters.models import BillingAccount
from basis.modules.billing.public import OwnerBilling
from basis.shared.identifiers import AccountId


def account_row(owner: int) -> BillingAccount:
    billing().ensure(OwnerBilling(AccountId(owner)))
    return BillingAccount.objects.get(owner_id=owner)


def mark_pending(owner: int) -> None:
    billing().mark_pending(OwnerBilling(AccountId(owner)))
