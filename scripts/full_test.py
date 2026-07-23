"""全面测试数据生成与功能验证脚本"""
import sys, os, re, random
sys.path.insert(0, '/workspace/tim-study-assistant')
import matplotlib; matplotlib.use('Agg')
from datetime import date, timedelta

from database import execute_db, query_db, init_db
from app import app

init_db()
c = app.test_client()
R = []  # 结果收集

def T(desc, ok, detail=''):
    R.append(('✅' if ok else '❌') + f' {desc} {detail}')
    if not ok: print(f'  ❌ {desc} {detail}')

# ===== 1. 生成测试数据 =====
print('=== 1. 生成测试数据 ===')
c.post('/login', data={'username':'tim','password':'tim123'})

# 获取 csrf
csrf = re.search(r'csrf-token" content="([^"]+)"', c.get('/').get_data(as_text=True)).group(1)

# 各学科典型错题
test_data = [
    ('数学', '(1) 8^x = 2^18，求 x 的值', 'x=6', 'x=6', '', '幂的乘方', 3, 'active'),
    ('数学', '(2) 比较 25^4, 125^3 的大小', '25^4<125^3', '25^4<125^3', '', '幂的乘方', 3, 'active'),
    ('数学', '解不等式 2x^2-5x-3>0', 'x>3', 'x<-1/2 或 x>3', '漏了负数解', '一元二次不等式', 3, 'active'),
    ('物理', 'R1=4Ω,R2=6Ω 并联，求总电阻', 'R=10Ω', 'R=2.4Ω', '并联公式记错', '电阻并联', 2, 'active'),
    ('物理', '物体从静止开始匀加速 a=2m/s^2，求 5s 位移', 's=10m', 's=25m', '漏了 1/2', '匀变速运动', 2, 'mastered'),
    ('英语', 'The book ___ on the desk. (lie)', 'lays', 'lies', 'lie/lay 混淆', '动词时态', 2, 'active'),
    ('英语', 'I ___ (go) to school yesterday.', 'go', 'went', '时态未改', '过去式', 1, 'mastered'),
    ('生物', '光合作用的场所是？', '线粒体', '叶绿体', '概念混淆', '光合作用', 2, 'active'),
    ('化学', '写出水的电解方程式', 'H2+O2=H2O', '2H2O=2H2↑+O2↑', '配平错误', '电解水', 3, 'active'),
    ('信奥', '写出快速排序的时间复杂度', 'O(n)', 'O(n log n)', '记忆错误', '排序算法', 4, 'active'),
]

uids = []
for xueke, timu, sda, zda, cwf, zd, diff, status in test_data:
    mid = execute_db(
        "INSERT INTO mistake_records(uuid,sys_platform,xueke,timu,xueshengdaan,zhengquedaan,cuowufenxi,zhishidian,difficulty,status,next_review_at,review_stage) VALUES(?,'web',?,?,?,?,?,?,?,?,date('now'),0)",
        ('test-data', xueke, timu, sda, zda, cwf, zd, diff, status))
    uids.append(mid)
T(f'生成 {len(uids)} 条测试错题', len(uids) == 10, f'IDs: {uids[0]}-{uids[-1]}')

# 学习计划
for title, kp in [('本周完成幂运算复习', '幂'), ('英语时态专项训练', '时态')]:
    c.post('/study-plans/add', data={'title':title,'zhishidian':kp,'xueke':'数学','priority':3,'csrf_token':csrf}, follow_redirects=True)
plans = query_db("SELECT * FROM study_plans WHERE status!='deleted'", ())
T('学习计划', len(plans) >= 2, f'{len(plans)} 条')

# 复习记录
for mid in uids[:5]:
    for i in range(random.randint(1,3)):
        r = random.choice(['correct','partial','incorrect'])
        execute_db("INSERT INTO review_logs(mistake_id,uuid,review_date,result,time_spent) VALUES(?,'test',date('now',?||' days'),?,?)",
                   (mid, str(-i), r, random.randint(30,300)))
T('复习记录', True)

# ===== 2. 页面测试 =====
print('\n=== 2. 页面测试 ===')
pages = {
    '/': '进行中的学习计划',
    '/questions': '幂的乘方',
    '/questions/add': '添加错题',
    '/statistics': '错误类型分布',
    '/review': '今日待复习',
    '/study-plans': 'calendar-grid',
    '/knowledge-matrix': 'progress-bar',
    '/knowledge-points': '掌握率',
    '/questions/deleted': '回收站',
}
for p, kw in pages.items():
    r = c.get(p)
    T(f'{p}', r.status_code == 200 and kw in r.get_data(as_text=True),
      f'HTTP{r.status_code}')

# ===== 3. API 测试 =====
print('\n=== 3. API 测试 ===')
# 批量更新
r = c.post('/api/questions/batch-update', json={'ids':[uids[0]],'action':'status','value':'mastered'},
           headers={'X-CSRF-Token':csrf})
T('批量更新', r.status_code == 200, f'HTTP{r.status_code}')

# 今日统计
r = c.get('/api/review/today-stats')
data = r.get_json()
T('今日统计', r.status_code == 200 and 'total' in data, str(data))

# 复习提交
r = c.post(f'/api/review/{uids[2]}/submit', json={'result':'correct','time_spent':60},
           headers={'X-CSRF-Token':csrf})
T('复习提交', r.status_code == 200, f'HTTP{r.status_code}')

# 导出
for fmt in ['excel','pdf','anki']:
    r = c.get(f'/api/export/{fmt}')
    T(f'导出{fmt}', r.status_code == 200, f'{len(r.get_data())}bytes')

# 计划关联复习
plan = query_db("SELECT id FROM study_plans LIMIT 1", one=True)
r = c.post(f'/api/study-plans/{plan["id"]}/review', headers={'X-CSRF-Token':csrf})
T('计划复习', r.status_code == 200, str(r.get_json()))

# 一键加入复习
r = c.post('/api/review/add-all', headers={'X-CSRF-Token':csrf})
T('一键复习', r.status_code == 200)

# ===== 4. 安全测试 =====
print('\n=== 4. 安全测试 ===')
c2 = app.test_client()
T('登录保护', c2.get('/').status_code == 302)
T('CSRF保护', c2.post('/study-plans/add', data={'title':'test'}).status_code == 403)
T('SQL注入', c.post('/api/questions/batch-update',
    json={'ids':[1],'action':"DROP TABLE"}, headers={'X-CSRF-Token':csrf}).status_code in (400,403))
T('错误密码', '错误' in c2.post('/login', data={'username':'tim','password':'bad'}).get_data(as_text=True))

# ===== 5. 软删除+回收站 =====
print('\n=== 5. 软删除+回收站 ===')
r = c.post(f'/questions/{uids[8]}/delete', data={'csrf_token':csrf})
T('删除错题', r.status_code in (200,302), f'HTTP{r.status_code}')
deleted = query_db("SELECT id FROM mistake_records WHERE status='deleted'", ())
T('软删除', len(deleted) >= 1, f'{len(deleted)} 条 deleted')
r = c.get('/questions/deleted')
T('回收站', r.status_code == 200 and '恢复' in r.get_data(as_text=True))

# ===== 汇总 =====
print(f'\n{"="*50}')
passed = sum(1 for r in R if '✅' in r)
print(f'通过: {passed}/{len(R)}')
for r in R:
    if '❌' in r: print(' ', r)

# 清理测试数据
execute_db("DELETE FROM mistake_records WHERE uuid='test-data'")
execute_db("DELETE FROM review_logs WHERE uuid='test'")
execute_db("DELETE FROM study_plans WHERE uuid='test-data'")
print('\n测试数据已清理')
