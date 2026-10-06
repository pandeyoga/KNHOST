"""G3 D4-TEST-01 — oracle ATP independen (rumus bisnis: tersedia + incoming(horizon) − permintaan tertunda)."""


def atp_mismatches(rows):
    bad = []
    for row in rows:
        exp = float(row.get('total_available') or 0) + float(row.get('total_incoming') or 0) \
            - float(row.get('total_pending_demand') or 0)
        if abs(exp - float(row.get('total_atp') or 0)) >= 0.01:
            bad.append({'sku': row.get('sku'), 'level': 'row', 'atp': row.get('total_atp'), 'expected': exp})
        for ent in row.get('by_entity', []):
            e = ent['available'] + ent['incoming'] - float(ent.get('pending_demand') or 0)
            if abs(e - ent['atp']) >= 0.01:
                bad.append({'sku': row.get('sku'), 'level': 'entity', 'entity': ent['entity_id'],
                            'atp': ent['atp'], 'expected': e})
            for wh in ent.get('by_warehouse', []):
                e = wh['available'] + wh['incoming'] - float(wh.get('pending_demand') or 0)
                if abs(e - wh['atp']) >= 0.01:
                    bad.append({'sku': row.get('sku'), 'level': 'wh', 'wh': wh['warehouse_id'],
                                'atp': wh['atp'], 'expected': e})
    return bad
