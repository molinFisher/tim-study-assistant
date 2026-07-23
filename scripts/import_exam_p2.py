"""
一次性脚本：从数学练习册第 2/20 页整理导入 11 道题目到错题数据库。
按主用户 uuid (27d14943...) 直接 INSERT。

运行：
    python3.11 scripts/import_exam_p2.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import init_db, execute_db, query_db


# 目标 uuid：当前主用户（DB 中记录数最多的 uuid）
TARGET_UUID = '27d14943-68fe-42cb-a046-fceb040864f2'  # 占位，先按数量最多取
FALLBACK_UUID = None  # 用 query_db 动态获取

# 11 道题目（全部 xueke=数学）
QUESTIONS = [
    {
        'timu': '(1) $8^x = 2^{18}$，求 $x$ 的值。',
        'xueshengdaan': '设 $8^x=(2^3)^x=2^{3x}=2^{18}$，$\\therefore 3x=18$，$x=6$',
        'zhengquedaan': '$x=6$',
        'cuowufenxi': '',
        'zhishidian': '幂的乘方；同底数幂相等',
        'difficulty': 3,
    },
    {
        'timu': '(2) [类比解答] 比较 $25^4$, $125^3$ 的大小。',
        'xueshengdaan': '$25^4=(5^2)^4=5^8$，$125^3=(5^3)^3=5^9$，$\\therefore 25^4<125^3$',
        'zhengquedaan': '$25^4<125^3$',
        'cuowufenxi': '',
        'zhishidian': '幂的乘方',
        'difficulty': 3,
    },
    {
        'timu': '(3) [拓展拔高] 比较 $3^{555}$, $4^{444}$, $5^{333}$ 的大小。',
        'xueshengdaan': '$3^{555}=(3^5)^{111}=243^{111}$，$4^{444}=(4^4)^{111}=256^{111}$，$5^{333}=(5^3)^{111}=125^{111}$；$125^{111}<243^{111}<256^{111}$，$\\therefore 5^{333}<3^{555}<4^{444}$',
        'zhengquedaan': '$5^{333}<3^{555}<4^{444}$',
        'cuowufenxi': '',
        'zhishidian': '同底数幂比较大小（多步比较）',
        'difficulty': 5,
    },
    {
        'timu': '9. 下列运算中正确的是（　）\nA. $(2ab)^3=2a^3b^3$\nB. $a^3\\cdot a^2=a^5$\nC. $a^6\\div a^3=a^3$\nD. $(a^3)^4=a^{12}$',
        'xueshengdaan': 'D',
        'zhengquedaan': 'B、C、D（多选）',
        'cuowufenxi': 'A 错（应为 $8a^3b^3$）；B、C、D 均正确',
        'zhishidian': '同底数幂的除法；幂的乘方；积的乘方',
        'difficulty': 2,
    },
    {
        'timu': '10. 下列计算正确的是（　）\nA. $a^2\\cdot a^3=a^5$\nB. $a^3+a^3=a^6$\nC. $a^8\\div a^4=a^4$\nD. $(a^3)^3=a^6$',
        'xueshengdaan': 'D',
        'zhengquedaan': 'A',
        'cuowufenxi': '学生误选 D：D 错误（$(a^3)^3=a^9$ 而非 $a^6$）；正确答案 A（$a^2\\cdot a^3=a^5$）',
        'zhishidian': '同底数幂的除法；幂的乘方',
        'difficulty': 2,
    },
    {
        'timu': '11. 若 $10^a=3$, $10^b=2$, 则 $10^{2a-b}=$?',
        'xueshengdaan': '$\\dfrac{9}{2}$',
        'zhengquedaan': '$\\dfrac{9}{2}$',
        'cuowufenxi': '',
        'zhishidian': '幂的运算（含字母指数）',
        'difficulty': 3,
    },
    {
        'timu': '12. 如图，在长为 $3a+2$、宽为 $2b-1$ 的长方形铁片上，挖去长为 $2a+4$、宽为 $b$ 的小长方形铁片，则剩余部分面积是（　）\nA. $6ab-3a+4b$\nB. $4ab-3a-2$\nC. $6ab-3a+8b-2$\nD. $4ab-3a+8b-2$',
        'xueshengdaan': 'B',
        'zhengquedaan': 'B',
        'cuowufenxi': '',
        'zhishidian': '多项式乘多项式；面积公式',
        'difficulty': 3,
    },
    {
        'timu': '13. 关于 $x$ 的代数式 $(3-ax)(3+2x)$ 的化简结果中不含 $x$ 的一次项，则 $a$ 的值是（　）\nA. 1  B. 2  C. 3  D. 4',
        'xueshengdaan': 'D',
        'zhengquedaan': 'B',
        'cuowufenxi': '学生误选 D：$(3-ax)(3+2x)=9+(6-3a)x-2ax^2$，令 $6-3a=0$，$a=2$，故正确答案为 B（$a=2$）',
        'zhishidian': '多项式乘多项式；合并同类项',
        'difficulty': 3,
    },
    {
        'timu': '14. 下列计算正确的是（　）\nA. $(a-1)^2=a^2-1$\nB. $(-a^2b)^2=-a^4b^2$\nC. $a^6+a^3=a^3$\nD. $(a^2)^3=a^6$',
        'xueshengdaan': 'D',
        'zhengquedaan': 'D',
        'cuowufenxi': '',
        'zhishidian': '完全平方公式；积的乘方；幂的乘方',
        'difficulty': 3,
    },
    {
        'timu': '15. 下列运算正确的是（　）\nA. $3a+a^2=3a^3$\nB. $(-3a^3)^2=6a^6$\nC. $a^2\\cdot a^3=a^6$\nD. $(a-b)^2=a^2-2ab+b^2$',
        'xueshengdaan': 'C',
        'zhengquedaan': 'D',
        'cuowufenxi': '学生误选 C：C 错误（$a^2\\cdot a^3=a^5$ 而非 $a^6$）；正确答案为 D（$(a-b)^2=a^2-2ab+b^2$）',
        'zhishidian': '完全平方公式；合并同类项；幂的运算',
        'difficulty': 3,
    },
    {
        'timu': '16. 下列运算正确的是（　）\nA. $(-a)^2=-a^2$\nB. $2a^2-a^2=a^2$\nC. $a^2\\cdot a=a^3$\nD. $(a+1)^2=a^2+1$',
        'xueshengdaan': 'C',
        'zhengquedaan': 'B、C（多选）',
        'cuowufenxi': 'A 错（应为 $a^2$）；D 错（应为 $a^2+2a+1$）；B、C 均正确',
        'zhishidian': '完全平方公式；幂的乘方',
        'difficulty': 3,
    },
]


def resolve_target_uuid():
    """取 mistake_records 中记录数最多的 uuid 作主用户；找不到则取 FALLBACK_UUID。"""
    rows = query_db(
        'SELECT uuid, COUNT(*) AS cnt FROM mistake_records GROUP BY uuid ORDER BY cnt DESC'
    )
    if rows and rows[0]['uuid']:
        return rows[0]['uuid']
    return FALLBACK_UUID or ''


def main():
    init_db()
    target_uuid = resolve_target_uuid()
    if not target_uuid:
        print('错误：找不到目标 uuid')
        return 1
    print(f'目标 uuid: {target_uuid}')

    # 显示当前数量
    before = query_db(
        'SELECT COUNT(*) AS cnt FROM mistake_records WHERE uuid = ?',
        (target_uuid,), one=True
    )['cnt']
    print(f'导入前记录数: {before}')

    inserted_ids = []
    for q in QUESTIONS:
        mid = execute_db(
            '''INSERT INTO mistake_records
               (uuid, sys_platform, xueke, timu, xueshengdaan, zhengquedaan,
                cuowufenxi, zhishidian, difficulty, status)
               VALUES (?, 'web', ?, ?, ?, ?, ?, ?, ?, 'active')''',
            (
                target_uuid,
                '数学',
                q['timu'],
                q['xueshengdaan'],
                q['zhengquedaan'],
                q['cuowufenxi'],
                q['zhishidian'],
                q['difficulty'],
            )
        )
        inserted_ids.append(mid)
        print(f'  +#{mid}  {q["timu"][:50]}...')

    after = query_db(
        'SELECT COUNT(*) AS cnt FROM mistake_records WHERE uuid = ?',
        (target_uuid,), one=True
    )['cnt']
    print(f'\n导入后记录数: {after}（新增 {after - before} 条）')
    print(f'新插入 id: {inserted_ids}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
