import csv, io, json, zipfile, urllib.request
from datetime import date, timedelta, datetime, timezone

URL='https://data.lpp.si/api/gtfs/feed.zip'
ROUTES={'27':'Konzorcij','11':'Drama','25':'Bavarski dvor'}
ORIGIN='polje'

def read(z,name):
    with z.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f,'utf-8-sig',newline='')))

def active_dates(calendar, exceptions):
    by={}
    for r in calendar:
        d=date.fromisoformat(r['start_date']); end=date.fromisoformat(r['end_date'])
        while d<=end:
            wd=['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][d.weekday()]
            if r.get(wd)=='1': by.setdefault(r['service_id'],set()).add(d.isoformat())
            d+=timedelta(days=1)
    for e in exceptions:
        s=by.setdefault(e['service_id'],set())
        if e['exception_type']=='1': s.add(e['date'])
        elif e['exception_type']=='2': s.discard(e['date'])
    return by

def mins(s):
    h,m,sec=map(int,s.split(':')); return h*60+m

def main():
    data=urllib.request.urlopen(URL,timeout=60).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        routes=read(z,'routes.txt'); stops=read(z,'stops.txt'); trips=read(z,'trips.txt'); sts=read(z,'stop_times.txt'); cal=read(z,'calendar.txt') if 'calendar.txt' in z.namelist() else []; exc=read(z,'calendar_dates.txt') if 'calendar_dates.txt' in z.namelist() else []
    route_ids={r['route_id']:r['route_short_name'] for r in routes if r.get('route_short_name') in ROUTES}
    stop_ids={r: set() for r in [ORIGIN]+list(ROUTES.values())}
    for s in stops:
        n=s.get('stop_name','').strip().casefold()
        if n in stop_ids: stop_ids[n].add(s['stop_id'])
    services=active_dates(cal,exc)
    # Group stop times by trip.
    grouped={}
    for x in sts:
        grouped.setdefault(x['trip_id'],[]).append(x)
    trip_info={t['trip_id']:t for t in trips if t['route_id'] in route_ids}
    days={}
    for tid,t in trip_info.items():
        seq=sorted(grouped.get(tid,[]), key=lambda x:int(float(x.get('stop_sequence','0'))))
        origins=[x for x in seq if x['stop_id'] in stop_ids[ORIGIN]]
        if not origins: continue
        for line,destname in ROUTES.items():
            if route_ids[t['route_id']]!=line: continue
            dests=[x for x in seq if x['stop_id'] in stop_ids[destname]]
            for o in origins:
                after=[d for d in dests if int(float(d['stop_sequence']))>int(float(o['stop_sequence']))]
                if not after: continue
                d=after[0]
                item={'dep':o['departure_time'][:5],'arr':d['arrival_time'][:5]}
                for day in services.get(t['service_id'],[]):
                    days.setdefault(day,{}).setdefault(line,[]).append(item)
                break
    for day in days:
        for line in days[day]:
            days[day][line].sort(key=lambda x:(mins(x['dep']),mins(x['arr'])))
    out={'generated_at':datetime.now(timezone.utc).isoformat(),'source':URL,'days':days}
    with open('data.json','w',encoding='utf-8') as f: json.dump(out,f,separators=(',',':'))

if __name__=='__main__': main()
