from dataclasses import dataclass, field


@dataclass
class TenderSummary:
    """Jedan red iz liste oglasa (rezultat pretrage po CPV kodu)."""

    tender_id: str
    title: str
    cpv_code: str
    buyer: str | None
    publish_date: str | None
    deadline: str | None
    detail_url: str


@dataclass
class TenderDocument:
    """Jedan prilog (PDF) konkursne dokumentacije."""

    dms_id: str
    file_name: str
    download_url: str
    local_path: str | None = None
    extracted_text: str | None = None


@dataclass
class Tender:
    """Puni tender: sazetak + preuzeti dokumenti."""

    summary: TenderSummary
    estimated_value: str | None = None
    documents: list[TenderDocument] = field(default_factory=list)
