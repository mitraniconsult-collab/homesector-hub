"""Pure Easyrea availability decisions; never alter inventory quantities."""
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Decision:
    action: str
    policy: str | None
    arrival: str | None
    reason: str


def arrival_date(value, today=None):
    if not isinstance(value, str):
        return None
    try:
        value = value.strip()
        parsed = date.fromisoformat(value) if len(value) == 10 else datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except ValueError:
        return None
    return parsed.isoformat() if parsed >= (today or date.today()) else None


def supplier_stopped(rec, stopped_ids=()):
    if str(rec.get('idTypeDispo')) in {'0'} | {str(x) for x in stopped_ids}:
        return True
    labels = [rec.get(k) for k in ('availabilityLabel', 'libelleTypeDispo', 'labelTypeDispo', 'typeDispo')]
    return any(isinstance(x, str) and x.strip().lower() in {
        'product stopped', 'stopped', 'discontinued', 'produit arrêté',
        'produit arrete', 'arrêté', 'arrete', 'спрян',
    } for x in labels)


def decide(rec, quantity, stopped_ids=(), today=None):
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        return Decision('REVIEW', None, None, 'Не е прочетено количеството в Shopify')
    if rec is None:
        return Decision('MISSING', 'DENY', None, 'Липсва в пълния Easyrea каталог; продава се само локална наличност')
    status = str(rec.get('idTypeDispo'))
    if supplier_stopped(rec, stopped_ids):
        return Decision('STOPPED', 'DENY', None, 'Спрян от доставчика; локалното количество се запазва')
    if status == '1':
        return Decision('IN_STOCK', 'CONTINUE', None, 'Наличен при доставчика')
    if status == '2':
        if quantity > 0:
            return Decision('LOCAL_STOCK', 'DENY', None, 'Продаваме само локалната наличност')
        arrival = arrival_date(rec.get('dateArrivage'), today)
        if arrival:
            return Decision('PREORDER', 'CONTINUE', arrival, 'Предварителна поръчка с очаквана дата при доставчика')
        return Decision('NO_VALID_DATE', 'DENY', None, 'Невалидна или минала дата; предварителните поръчки са спрени')
    return Decision('REVIEW', None, None, f'Непознат Easyrea статус {status} — без промяна')


def product_date(decisions, complete=True):
    if not complete or any(d.policy is None for d in decisions):
        return False, None, 'Непълни/непознати варианти — продуктовата дата не се променя'
    dates = {d.arrival for d in decisions}
    if len(dates) == 1:
        return True, next(iter(dates)), ''
    return True, None, 'Различни дати/наличности: датите са по варианти; продуктовата дата се изчиства'
