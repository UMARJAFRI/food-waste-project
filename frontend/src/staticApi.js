const STORE_KEY='harvest-food-records-v1';
const meals=['Breakfast','Lunch','Dinner'];
const foods={Breakfast:['Poha','Idli sambar','Upma','Paratha','Dosa'],Lunch:['Rice & dal','Veg pulao','Rajma chawal','Chapati & curry','Khichdi'],Dinner:['Roti & paneer','Veg biryani','Dal rice','Pasta','Mixed thali']};
const isoDay=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;

function seed(){
  const today=new Date(), records=[];
  for(let offset=39;offset>=0;offset--){
    const date=new Date(today);date.setDate(date.getDate()-offset);
    meals.forEach((meal,mi)=>{
      const people=48+((offset*13+mi*19)%64);
      const prepared=Number((people*(mi===0?.19:.31)+((offset+mi)%5)*.8).toFixed(1));
      const ratio=.91-((offset*7+mi*11)%23)/100;
      const consumed=Math.min(prepared,Number((prepared*ratio).toFixed(1)));
      records.push({id:records.length+1,date:isoDay(date),meal_type:meal,food_name:foods[meal][(offset+mi)%foods[meal].length],people_expected:people,prepared,consumed,leftover:Number((prepared-consumed).toFixed(1)),is_demo:1});
    });
  }
  return records;
}
function read(){
  try{const raw=localStorage.getItem(STORE_KEY);if(raw){const parsed=JSON.parse(raw);if(Array.isArray(parsed))return parsed}}catch{}
  const data=seed();write(data);return data;
}
function write(data){try{localStorage.setItem(STORE_KEY,JSON.stringify(data))}catch{}}
function fail(message){throw new Error(message)}
function filterRecords(data,params){
  let result=[...data];const search=(params.get('search')||'').toLowerCase(),meal=params.get('meal'),start=params.get('start'),end=params.get('end');
  if(search)result=result.filter(r=>`${r.food_name} ${r.meal_type}`.toLowerCase().includes(search));
  if(meals.includes(meal))result=result.filter(r=>r.meal_type===meal);
  if(start)result=result.filter(r=>r.date>=start);if(end)result=result.filter(r=>r.date<=end);
  return result.sort((a,b)=>b.date.localeCompare(a.date)||b.id-a.id);
}
function dashboard(data,params){
  const selected=filterRecords(data,new URLSearchParams(`start=${encodeURIComponent(params.get('start')||'')}&end=${encodeURIComponent(params.get('end')||'')}`));
  const prepared=selected.reduce((s,r)=>s+r.prepared,0),consumed=selected.reduce((s,r)=>s+r.consumed,0),wasted=selected.reduce((s,r)=>s+r.prepared-r.consumed,0);
  const byDate={},byMeal={};
  selected.forEach(r=>{const d=byDate[r.date]||={date:r.date,prepared:0,consumed:0,wasted:0};d.prepared+=r.prepared;d.consumed+=r.consumed;d.wasted+=r.prepared-r.consumed;const m=byMeal[r.meal_type]||={meal_type:r.meal_type,prepared:0,consumed:0,wasted:0};m.prepared+=r.prepared;m.consumed+=r.consumed;m.wasted+=r.prepared-r.consumed});
  const roundRows=items=>items.map(x=>Object.fromEntries(Object.entries(x).map(([k,v])=>[k,typeof v==='number'?Number(v.toFixed(1)):v])));
  return{summary:{records:selected.length,prepared:Number(prepared.toFixed(1)),consumed:Number(consumed.toFixed(1)),wasted:Number(wasted.toFixed(1)),waste_pct:prepared?Number((wasted/prepared*100).toFixed(1)):0},daily:roundRows(Object.values(byDate).sort((a,b)=>a.date.localeCompare(b.date))),meals:roundRows(meals.filter(m=>byMeal[m]).map(m=>byMeal[m])),recent:filterRecords(data,new URLSearchParams()).slice(0,6)};
}
function recommendations(data){
  const prepared=data.reduce((s,r)=>s+r.prepared,0),wasted=data.reduce((s,r)=>s+r.prepared-r.consumed,0),pct=prepared?wasted/prepared*100:0;
  const grouped=meals.map(meal=>{const rows=data.filter(r=>r.meal_type===meal),p=rows.reduce((s,r)=>s+r.prepared,0),w=rows.reduce((s,r)=>s+r.prepared-r.consumed,0);return{meal_type:meal,prepared:p,wasted:w,rate:p?w/p*100:0}});
  const highest=grouped.sort((a,b)=>b.rate-a.rate)[0],tips=[];
  if(highest?.prepared&&highest.rate>10)tips.push({type:'alert',title:`Review ${highest.meal_type.toLowerCase()} preparation`,text:`${highest.meal_type} has the highest waste rate (${highest.rate.toFixed(1)}%). Reduce the next batch by 5–10% and review attendance.`});
  if(pct>10)tips.push({type:'alert',title:'Trim overproduction gradually',text:'Overall waste is above 10%. Prepare smaller replenishable batches and compare leftovers after each service.'});
  tips.push({type:'plan',title:'Plan from attendance',text:'Use class schedules, events and hostel headcounts to estimate covers before finalising quantities.'},{type:'track',title:'Track meal patterns',text:'Record leftovers by meal and dish consistently. Repeat low-waste recipes and adjust only where the data shows a pattern.'},{type:'store',title:'Store food safely',text:'Label, cool and store eligible surplus promptly under local food safety guidance.'},{type:'share',title:'Share safe surplus responsibly',text:'Where permitted, coordinate timely donation of safe, untouched surplus with an approved local organisation.'},{type:'portion',title:'Encourage mindful portions',text:'Offer smaller first servings with easy seconds, and make portion sizes clear to diners.'});
  return{waste_pct:Number(pct.toFixed(1)),prepared:Number(prepared.toFixed(1)),wasted:Number(wasted.toFixed(1)),highest_meal:highest?.meal_type,recommendations:tips};
}
function predict(data,body){
  const meal=body.meal_type,people=Number(body.people_expected),historicalPrepared=Number(body.historical_prepared||0),historicalConsumed=Number(body.historical_consumed||0);
  if(!meals.includes(meal)||!Number.isInteger(people)||people<1)fail('Choose a meal and enter at least one expected person.');
  const history=data.filter(r=>r.meal_type===meal&&r.people_expected>0),perPerson=history.reduce((s,r)=>s+r.consumed/r.people_expected,0)/Math.max(history.length,1);let expected,source;
  if(history.length>=3&&perPerson){expected=perPerson*people;source=`Based on ${history.length} ${meal.toLowerCase()} records in your browser data, using average consumption per person.`}
  else if(historicalConsumed>0){expected=historicalConsumed;source='Estimate only: fewer than 3 matching records are available, so the entered historical average consumed quantity is used.'}
  else{expected=(historicalPrepared>0?historicalPrepared/people:(meal==='Breakfast'?.20:.30))*people;source='Estimate only: fewer than 3 matching records are available, so the entered historical prepared average or a simple meal-size estimate is used.'}
  expected=Number(expected.toFixed(1));const recommended=Number((expected*1.03).toFixed(1)),usedPrepared=Number((historicalPrepared>0?historicalPrepared:recommended).toFixed(1)),leftover=Number(Math.max(usedPrepared-expected,0).toFixed(1)),pct=usedPrepared?Number((leftover/usedPrepared*100).toFixed(1)):0;
  return{date:body.date,meal_type:meal,people_expected:people,expected_consumption:expected,expected_leftover:leftover,recommended_preparation:recommended,estimated_waste_pct:pct,waste_status:pct<5?'Low':pct<=10?'Moderate':'High',source,prepared_quantity_used:usedPrepared};
}
export async function staticApi(path,opts={}){
  const url=new URL(path,'https://local.invalid');url.pathname=url.pathname.replace(/^\/api(?=\/|$)/,'');const method=(opts.method||'GET').toUpperCase(),body=opts.body?JSON.parse(opts.body):{};let data=read();
  if(url.pathname==='/health')return{ok:true,database:'Browser local storage'};
  if(url.pathname==='/records'&&method==='GET')return filterRecords(data,url.searchParams).map(r=>({...r,leftover:Number((r.prepared-r.consumed).toFixed(2))}));
  if(url.pathname==='/records'&&method==='POST'){
    const values=validate(body),id=data.reduce((n,r)=>Math.max(n,r.id),0)+1;data.push({id,...values,is_demo:0});write(data);return{id,message:'Food record added.'};
  }
  const match=url.pathname.match(/^\/records\/(\d+)$/);
  if(match&&method==='PUT'){
    const id=Number(match[1]),index=data.findIndex(r=>r.id===id);if(index<0)fail('Record not found.');data[index]={id,...validate(body),is_demo:0};write(data);return{message:'Food record updated.'};
  }
  if(match&&method==='DELETE'){
    const id=Number(match[1]),next=data.filter(r=>r.id!==id);if(next.length===data.length)fail('Record not found.');write(next);return{message:'Food record deleted.'};
  }
  if(url.pathname==='/dashboard'&&method==='GET')return dashboard(data,url.searchParams);
  if(url.pathname==='/predict'&&method==='POST')return predict(data,body);
  if(url.pathname==='/recommendations'&&method==='GET')return recommendations(data);
  fail('This action is not available in the browser demo.');
}
function validate(x){
  const date=String(x.date||''),meal_type=String(x.meal_type||''),food_name=String(x.food_name||'').trim(),people_expected=Number(x.people_expected),prepared=Number(x.prepared),consumed=Number(x.consumed);
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!meals.includes(meal_type)||!food_name||!Number.isInteger(people_expected)||people_expected<1||!Number.isFinite(prepared)||prepared<=0||!Number.isFinite(consumed)||consumed<0||consumed>prepared)fail('Check meal, food name, people and quantities. Consumed must be between zero and prepared.');
  return{date,meal_type,food_name,people_expected,prepared,consumed,leftover:Number((prepared-consumed).toFixed(2))};
}
