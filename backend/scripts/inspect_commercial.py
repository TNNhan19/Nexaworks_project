import json
from pathlib import Path
from collections import defaultdict

data = json.loads(Path('../data/candidate_dataset.json').read_text(encoding='utf-8'))
opts = data.get('commercial_options', [])
print(f'Total commercial options: {len(opts)}')

groups = defaultdict(list)
for o in opts:
    groups[o['work_item_id']].append(o)
print(f'Opportunity work items: {sorted(groups.keys())}')
print()

for wid in sorted(groups.keys()):
    print(f'=== {wid} ===')
    for o in groups[wid]:
        oid = o['option_id']
        label = o.get('label')
        price = o.get('price_jpy')
        cost = o.get('direct_cost_jpy', 0)
        dhours = o.get('delivery_hours')
        pdays = o.get('payment_days')
        prob = o.get('estimated_win_probability')
        fov = o.get('follow_on_value_jpy', 0)
        warranty = o.get('warranty_months')
        deps = o.get('dependencies', [])
        print(f'  option_id={oid}  price={price}  cost={cost}  delivery_h={dhours}  prob={prob}  follow_on={fov}  payment_days={pdays}  deps={deps}')
        if isinstance(label, dict):
            print(f'    label(en)={label.get("en")}')
        else:
            print(f'    label={label}')

# Also show work items that are sales_opportunity type
print()
print('=== Work items of type sales_opportunity ===')
for w in data['work_items']:
    if w.get('type') == 'sales_opportunity':
        wid = w['id']
        title = w.get('title', {})
        en_title = title.get('en', str(title)) if isinstance(title, dict) else title
        due = w.get('due_date')
        mandatory = w.get('mandatory')
        hours = w.get('required_hours')
        direct_cost = w.get('direct_cost_jpy', 0)
        cash_in_days = w.get('cash_in_days')
        deps = w.get('dependencies', [])
        print(f'  {wid}: due={due} mandatory={mandatory} required_hours={hours} direct_cost={direct_cost} cash_in_days={cash_in_days} deps={deps}')
        print(f'    title={en_title}')
