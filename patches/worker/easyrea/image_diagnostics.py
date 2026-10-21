"""Stable, operator-facing reasons shared by the worker, UI and CSV report."""

class ImageReview(ValueError):
    def __init__(self, code, message, action, **details):
        super().__init__(message)
        self.code = code
        self.action = action
        self.details = details

def describe(row):
    item = dict(row)
    result = item.get('result', 'pending')
    defaults = {
        'pending': ('PENDING', 'scan', 'Продуктът изчаква обработка.', 'Изчакай задачата.'),
        'ADDED': ('IMAGES_ADDED', 'completed', 'Новите снимки са потвърдени в Shopify.', 'Не е необходимо действие.'),
        'IMPROVED': ('IMAGES_IMPROVED', 'completed', 'По-добрите снимки са потвърдени; одобрените стари снимки са отделени от продукта.', 'Не е необходимо действие.'),
        'PLANNED': ('DRY_RUN', 'completed', 'Намерени са снимки. Тестовият режим не качва в Shopify.', 'Стартирай реален режим за качване.'),
        'UNCHANGED': ('NO_IMPROVEMENT', 'completed', 'Няма одобрени нови или по-добри снимки.', 'Прегледай оригиналите само ако галерията още е непълна.'),
        'REVIEW_VARIANTS': ('MULTIPLE_VARIANTS', 'scan', 'Продуктът има няколко варианта и изисква проверка на снимките по цвят/модел.', 'Провери SKU/EAN и снимките на всеки вариант; автоматичното качване е за продукти с един вариант.'),
        'REVIEW_NO_SKU': ('LEGACY_NO_SKU', 'scan', 'Предишната версия е спряла поради липсващ SKU.', 'Стартирай нова задача: вече се търси и само по EAN. Ако липсва и EAN, добави поне един идентификатор.'),
        'REVIEW_NO_IDENTIFIER': ('NO_IDENTIFIER', 'scan', 'Липсват и SKU, и EAN/баркод.', 'Добави SKU или EAN в Shopify и стартирай нова задача.'),
        'REVIEW_CLEANUP': ('CLEANUP_UNCONFIRMED', 'cleanup', 'Новите снимки са качени, но отделянето на старите не е потвърдено.', 'Провери галерията в Shopify. Старите файлове са запазени; не повтаряй качването.'),
        'REVIEW_VARIANT_MEDIA': ('VARIANT_IMAGE_UNCONFIRMED', 'cleanup', 'Новите снимки са качени, но снимката на варианта не е потвърдена.', 'Провери коя снимка е зададена на варианта в Shopify.'),
        'REVIEW_UNCERTAIN': ('UPLOAD_UNCONFIRMED', 'upload', 'Не е потвърдено дали предишното качване е завършило.', 'Провери галерията в Shopify преди нов опит, за да избегнеш дубликати.'),
        'REVIEW_MEDIA_FAILED': ('SHOPIFY_MEDIA_FAILED', 'upload', 'Shopify е отказал обработката на поне една снимка.', 'Провери грешката на снимката в Shopify и достъпността на оригинала.'),
        'REVIEW': ('CHECK_REQUIRED', item.get('stage', 'process'), 'Обработката е спряна за проверка.', 'Прегледай посочената причина, коригирай данните и стартирай нова задача.'),
    }
    code, stage, note, action = defaults.get(result, defaults['REVIEW'])
    # Historical reports did not record a more specific source-failure reason.
    if result == 'REVIEW' and str(item.get('note', '')).startswith('Няма еднозначно съвпадение'):
        code, stage = 'LEGACY_SOURCE_UNRESOLVED', 'source'
        action = 'Стартирай нова задача за търсене по SKU и EAN с подробен резултат. Старият отчет не различава липса на продукт от несъответствие.'
    elif result == 'REVIEW' and str(item.get('note', '')).startswith('OpenAI:'):
        code, stage = 'AI_PRODUCT_UNCONFIRMED', 'ai'
        action = 'Сравни заглавие, размер, цвят и модела с линка към оригинала. При верни данни стартирай нова проверка.'
    item.setdefault('reason_code', code)
    item.setdefault('stage', stage)
    if not item.get('note'): item['note'] = note
    if result == 'REVIEW_NO_SKU' and item.get('barcode'):
        item['note'] = 'Предишната версия е пропуснала продукта без SKU, въпреки наличния EAN ' + item['barcode'] + '.'
    if result in ('REVIEW_CLEANUP', 'REVIEW_VARIANT_MEDIA'): item['note'] = note
    item.setdefault('action', action)
    return item
