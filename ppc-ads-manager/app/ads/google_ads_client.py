"""Google Ads API access, behind a small interface so the rest of the app
never has to know whether it's talking to a real account or the local mock.

Set GOOGLE_ADS_MODE=live and the GOOGLE_ADS_* credentials in .env to use the
real API (requires `pip install google-ads`). Defaults to `mock`, which is
enough to run the whole app — campaign creation, keyword sync, and bid/budget
changes all happen against the local JSON store instead of a live account.
"""

from abc import ABC, abstractmethod

from app.config import (
    GOOGLE_ADS_CLIENT_ID,
    GOOGLE_ADS_CLIENT_SECRET,
    GOOGLE_ADS_DEVELOPER_TOKEN,
    GOOGLE_ADS_LOGIN_CUSTOMER_ID,
    GOOGLE_ADS_MODE,
    GOOGLE_ADS_REFRESH_TOKEN,
)
from app.models import AdGroupState, Campaign, KeywordState


class AdsClient(ABC):
    """Every mutation the optimizer or campaign builder needs to make against
    a Google Ads account. Implementations must be idempotent-ish: called with
    the current local state, they reconcile the remote account to match."""

    @abstractmethod
    def sync_campaign(self, campaign: Campaign, ad_groups: list[AdGroupState], keywords: list[KeywordState]) -> None:
        """Push a freshly generated campaign structure to the account."""

    @abstractmethod
    def pause_keyword(self, keyword: KeywordState) -> None: ...

    @abstractmethod
    def set_keyword_bid(self, keyword: KeywordState, new_max_cpc: float) -> None: ...

    @abstractmethod
    def set_campaign_budget(self, campaign: Campaign, new_daily_budget: float) -> None: ...

    @abstractmethod
    def pause_ad_group(self, ad_group: AdGroupState) -> None: ...


class MockAdsClient(AdsClient):
    """No remote account — the local JSON store (app.store) already *is* the
    account. These methods exist so the optimizer's code path is identical
    between mock and live; here they're just log statements."""

    def sync_campaign(self, campaign, ad_groups, keywords) -> None:
        print(f"[mock-ads] synced campaign '{campaign.name}' "
              f"({len(ad_groups)} ad groups, {len(keywords)} keywords)")

    def pause_keyword(self, keyword: KeywordState) -> None:
        print(f"[mock-ads] paused keyword '{keyword.text}' ({keyword.match_type})")

    def set_keyword_bid(self, keyword: KeywordState, new_max_cpc: float) -> None:
        print(f"[mock-ads] set bid for '{keyword.text}' to ${new_max_cpc:.2f}")

    def set_campaign_budget(self, campaign: Campaign, new_daily_budget: float) -> None:
        print(f"[mock-ads] set daily budget for '{campaign.name}' to ${new_daily_budget:.2f}")

    def pause_ad_group(self, ad_group: AdGroupState) -> None:
        print(f"[mock-ads] paused ad group '{ad_group.name}'")


class LiveAdsClient(AdsClient):
    """Thin wrapper around the official `google-ads` client library.

    This talks to a real Google Ads account and will spend real money —
    every method below performs an actual mutate operation. Requires
    `pip install google-ads` and a full set of OAuth + developer token
    credentials (see .env.example). Resource-name construction follows the
    Google Ads API v18 mutate patterns; adjust `customer_id` handling if your
    account structure (MCC vs. direct) differs.
    """

    def __init__(self) -> None:
        try:
            from google.ads.googleads.client import GoogleAdsClient as _GAClient
        except ImportError as exc:  # pragma: no cover - only hit in live mode
            raise RuntimeError(
                "GOOGLE_ADS_MODE=live requires the google-ads package: pip install google-ads"
            ) from exc

        self._client = _GAClient.load_from_dict(
            {
                "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id": GOOGLE_ADS_CLIENT_ID,
                "client_secret": GOOGLE_ADS_CLIENT_SECRET,
                "refresh_token": GOOGLE_ADS_REFRESH_TOKEN,
                "login_customer_id": GOOGLE_ADS_LOGIN_CUSTOMER_ID,
                "use_proto_plus": True,
            }
        )

    def sync_campaign(self, campaign, ad_groups, keywords) -> None:
        # A full implementation builds CampaignOperation / AdGroupOperation /
        # AdGroupCriterionOperation / AdGroupAdOperation batches and submits
        # them via the CampaignService/AdGroupService/GoogleAdsService mutate
        # RPCs. Left as a structural stub — wire up customer_id and resource
        # names for your account before flipping GOOGLE_ADS_MODE=live.
        raise NotImplementedError(
            "LiveAdsClient.sync_campaign needs account-specific resource-name "
            "wiring before use. See google-ads-python examples for "
            "basic_operations/add_campaigns.py and add_ad_groups.py."
        )

    def pause_keyword(self, keyword: KeywordState) -> None:
        raise NotImplementedError("Wire up AdGroupCriterionOperation with status=PAUSED.")

    def set_keyword_bid(self, keyword: KeywordState, new_max_cpc: float) -> None:
        raise NotImplementedError("Wire up AdGroupCriterionOperation.cpc_bid_micros update.")

    def set_campaign_budget(self, campaign: Campaign, new_daily_budget: float) -> None:
        raise NotImplementedError("Wire up CampaignBudgetOperation.amount_micros update.")

    def pause_ad_group(self, ad_group: AdGroupState) -> None:
        raise NotImplementedError("Wire up AdGroupOperation with status=PAUSED.")


_client: AdsClient | None = None


def get_ads_client() -> AdsClient:
    global _client
    if _client is None:
        _client = LiveAdsClient() if GOOGLE_ADS_MODE == "live" else MockAdsClient()
    return _client
