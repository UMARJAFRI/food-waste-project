from datetime import date, timedelta
from pathlib import Path
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DB_PATH = Path(__file__).with_name('food_waste.db')
MEALS = {'Breakfast', 'Lunch', 'Dinner'}

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS food_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            meal_type TEXT NOT NULL, food_name TEXT NOT NULL,
            people_expected INTEGER NOT NULL, prepared REAL NOT NULL,
            consumed REAL NOT NULL, is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        if db.execute('SELECT COUNT(*) FROM food_records').fetchone()[0] == 0:
            foods = {'Breakfast':['Poha','Idli sambar','Upma','Paratha','Dosa'], 'Lunch':['Rice & dal','Veg pulao','Rajma chawal','Chapati & curry','Khichdi'], 'Dinner':['Roti & paneer','Veg biryani','Dal rice','Pasta','Mixed thali']}
            base = date.today()
            for offset in range(39, -1, -1):
                day = base - timedelta(days=offset)
                for mi, meal in enumerate(('Breakfast','Lunch','Dinner')):
                    people = 48 + ((offset * 13 + mi * 19) % 64)
                    prepared = round(people * (0.19 if mi == 0 else 0.31) + ((offset + mi) % 5) * 0.8, 1)
                    ratio = 0.91 - ((offset * 7 + mi * 11) % 23) / 100
                    consumed = round(prepared * ratio, 1)
                    db.execute('INSERT INTO food_records(date,meal_type,food_name,people_expected,prepared,consumed,is_demo) VALUES(?,?,?,?,?,?,1)',
                        (day.isoformat(), meal, foods[meal][(offset + mi) % len(foods[meal])], people, prepared, min(prepared, consumed)))

def clean_record(data):
    try:
        day = str(data.get('date', '')).strip()
        date.fromisoformat(day)
        meal = str(data.get('meal_type', '')).strip()
        name = str(data.get('food_name', '')).strip()
        people = int(data.get('people_expected', 0))
        prepared = round(float(data.get('prepared', 0)), 2)
        consumed = round(float(data.get('consumed', 0)), 2)
        if meal not in MEALS or not name or people < 1 or prepared <= 0 or consumed < 0 or consumed > prepared:
            raise ValueError('Check meal, food name, people and quantities. Consumed must be between zero and prepared.')
        return (day, meal, name, people, prepared, consumed)
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc) or 'Please enter valid record details.')

def rows(sql, params=()):
    with connect() as db:
        return [dict(r) for r in db.execute(sql, params).fetchall()]

@app.get('/api/health')
def health(): return jsonify({'ok': True, 'database': 'SQLite'})

@app.get('/api/records')
def get_records():
    search = request.args.get('search', '').strip()
    meal = request.args.get('meal', '').strip()
    start, end = request.args.get('start'), request.args.get('end')
    query = 'SELECT * FROM food_records WHERE 1=1'; args = []
    if search: query += ' AND (food_name LIKE ? OR meal_type LIKE ?)'; args += [f'%{search}%', f'%{search}%']
    if meal in MEALS: query += ' AND meal_type=?'; args.append(meal)
    if start: query += ' AND date>=?'; args.append(start)
    if end: query += ' AND date<=?'; args.append(end)
    query += ' ORDER BY date DESC, id DESC'
    result = rows(query, args)
    for item in result: item['leftover'] = round(item['prepared'] - item['consumed'], 2)
    return jsonify(result)

@app.post('/api/records')
def add_record():
    try:
        values = clean_record(request.get_json(force=True))
        with connect() as db: cur = db.execute('INSERT INTO food_records(date,meal_type,food_name,people_expected,prepared,consumed,is_demo) VALUES(?,?,?,?,?,?,0)', values)
        return jsonify({'id': cur.lastrowid, 'message': 'Food record added.'}), 201
    except (ValueError, TypeError) as e: return jsonify({'error': str(e)}), 400

@app.put('/api/records/<int:record_id>')
def edit_record(record_id):
    try:
        values = clean_record(request.get_json(force=True))
        with connect() as db:
            cur = db.execute('UPDATE food_records SET date=?,meal_type=?,food_name=?,people_expected=?,prepared=?,consumed=?,is_demo=0 WHERE id=?', (*values, record_id))
        if not cur.rowcount: return jsonify({'error':'Record not found.'}), 404
        return jsonify({'message':'Food record updated.'})
    except (ValueError, TypeError) as e: return jsonify({'error': str(e)}), 400

@app.delete('/api/records/<int:record_id>')
def delete_record(record_id):
    with connect() as db: cur = db.execute('DELETE FROM food_records WHERE id=?', (record_id,))
    if not cur.rowcount: return jsonify({'error':'Record not found.'}), 404
    return jsonify({'message':'Food record deleted.'})

@app.get('/api/dashboard')
def dashboard():
    start = request.args.get('start'); end = request.args.get('end')
    clause=''; args=[]
    if start: clause+=' AND date>=?'; args.append(start)
    if end: clause+=' AND date<=?'; args.append(end)
    summary = rows(f'SELECT COUNT(*) records, COALESCE(SUM(prepared),0) prepared, COALESCE(SUM(consumed),0) consumed, COALESCE(SUM(prepared-consumed),0) wasted FROM food_records WHERE 1=1{clause}', args)[0]
    summary['waste_pct'] = round(summary['wasted'] / summary['prepared'] * 100, 1) if summary['prepared'] else 0
    daily = rows(f'''SELECT date, ROUND(SUM(prepared),1) prepared, ROUND(SUM(consumed),1) consumed,
        ROUND(SUM(prepared-consumed),1) wasted FROM food_records WHERE 1=1{clause} GROUP BY date ORDER BY date''', args)
    meals = rows(f'''SELECT meal_type, ROUND(SUM(prepared),1) prepared, ROUND(SUM(consumed),1) consumed,
        ROUND(SUM(prepared-consumed),1) wasted FROM food_records WHERE 1=1{clause} GROUP BY meal_type''', args)
    recent = rows('SELECT * FROM food_records ORDER BY date DESC,id DESC LIMIT 6')
    for r in recent: r['leftover'] = round(r['prepared']-r['consumed'],1)
    return jsonify({'summary':summary,'daily':daily,'meals':meals,'recent':recent})

@app.post('/api/predict')
def predict():
    data=request.get_json(force=True)
    try:
        meal=data.get('meal_type'); people=int(data.get('people_expected',0)); prepared=float(data.get('historical_prepared',0) or 0); historical_consumed=float(data.get('historical_consumed',0) or 0)
        if meal not in MEALS or people<1: raise ValueError('Choose a meal and enter at least one expected person.')
        hist=rows('SELECT AVG(consumed*1.0/people_expected) per_person, AVG(prepared*1.0/people_expected) prep_person, COUNT(*) n FROM food_records WHERE meal_type=? AND people_expected>0',(meal,))[0]
        if hist['n'] >= 3 and hist['per_person']:
            per_person=hist['per_person']; source=f"Based on {hist['n']} {meal.lower()} records in your database, using average consumption per person."
        else:
            if historical_consumed > 0:
                expected = historical_consumed
                source='Estimate only: fewer than 3 matching records are available, so the entered historical average consumed quantity is used.'
            else:
                per_person=prepared / max(people,1) if prepared>0 else (0.20 if meal=='Breakfast' else 0.30)
                expected=per_person*people
                source='Estimate only: fewer than 3 matching records are available, so the entered historical prepared average or a simple meal-size estimate is used.'
        if hist['n'] >= 3 and hist['per_person']:
            expected=per_person*people
        expected=round(expected,1)
        # Add a modest 3% buffer to expected consumption to avoid routine shortfalls.
        recommended=round(expected*1.03,1)
        used_prepared=round(prepared,1) if prepared>0 else recommended
        leftover=round(max(used_prepared-expected,0),1)
        pct=round(leftover/used_prepared*100,1) if used_prepared else 0
        status='Low' if pct<5 else ('Moderate' if pct<=10 else 'High')
        return jsonify({'date':data.get('date'),'meal_type':meal,'people_expected':people,'expected_consumption':expected,'expected_leftover':leftover,'recommended_preparation':recommended,'estimated_waste_pct':pct,'waste_status':status,'source':source,'prepared_quantity_used':used_prepared})
    except (TypeError, ValueError) as e: return jsonify({'error':str(e)}),400

@app.get('/api/recommendations')
def recommendations():
    summary=rows('SELECT COALESCE(SUM(prepared),0) prepared, COALESCE(SUM(prepared-consumed),0) wasted FROM food_records')[0]
    pct=summary['wasted']/summary['prepared']*100 if summary['prepared'] else 0
    by_meal=rows('SELECT meal_type, SUM(prepared-consumed) wasted, SUM(prepared) prepared, COUNT(*) n FROM food_records GROUP BY meal_type')
    highest=max(by_meal,key=lambda x:x['wasted']/x['prepared'] if x['prepared'] else 0,default=None)
    tips=[]
    if highest and highest['prepared'] and highest['wasted']/highest['prepared']*100>10:
        tips.append({'type':'alert','title':f"Review {highest['meal_type'].lower()} preparation",'text':f"{highest['meal_type']} has the highest waste rate ({highest['wasted']/highest['prepared']*100:.1f}%). Reduce the next batch by 5–10% and review attendance."})
    if pct>10: tips.append({'type':'alert','title':'Trim overproduction gradually','text':'Overall waste is above 10%. Prepare smaller replenishable batches and compare leftovers after each service.'})
    tips += [
      {'type':'plan','title':'Plan from attendance','text':'Use class schedules, events and hostel headcounts to estimate covers before finalising quantities.'},
      {'type':'track','title':'Track meal patterns','text':'Record leftovers by meal and dish consistently. Repeat low-waste recipes and adjust only where the data shows a pattern.'},
      {'type':'store','title':'Store food safely','text':'Label, cool and store eligible surplus promptly under local food safety guidance.'},
      {'type':'share','title':'Share safe surplus responsibly','text':'Where permitted, coordinate timely donation of safe, untouched surplus with an approved local organisation.'},
      {'type':'portion','title':'Encourage mindful portions','text':'Offer smaller first servings with easy seconds, and make portion sizes clear to diners.'}]
    return jsonify({'waste_pct':round(pct,1),'prepared':round(summary['prepared'],1),'wasted':round(summary['wasted'],1),'highest_meal':highest['meal_type'] if highest else None,'recommendations':tips})

init_db()
if __name__ == '__main__': app.run(debug=True, port=5000)
