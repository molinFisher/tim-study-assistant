"""重新用纯文本导入 11 道题（无 LaTeX 标记）"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from database import execute_db, query_db

uuid = query_db('SELECT uuid FROM mistake_records LIMIT 1', one=True)['uuid']

qs = [
    ('(1) 8^x = 2^18，求 x 的值。', '设 8^x=(2^3)^x=2^(3x)=2^18，∴3x=18，x=6', 'x=6', '', '幂的乘方；同底数幂相等', 3),
    ('(2) [类比解答] 比较 25^4, 125^3 的大小。', '25^4=(5^2)^4=5^8，125^3=(5^3)^3=5^9，∴25^4<125^3', '25^4<125^3', '', '幂的乘方', 3),
    ('(3) [拓展拔高] 比较 3^555, 4^444, 5^333 的大小。', '3^555=(3^5)^111=243^111，4^444=(4^4)^111=256^111，5^333=(5^3)^111=125^111；125^111<243^111<256^111，∴5^333<3^555<4^444', '5^333<3^555<4^444', '', '同底数幂比较大小（多步比较）', 5),
    ('9.\nA. (2ab)^3=2a^3b^3\nB. a^3·a^2=a^5\nC. a^6÷a^3=a^3\nD. (a^3)^4=a^12', 'D', 'B、C、D（多选）', 'A 错（应为 8a^3b^3）', '同底数幂的除法；幂的乘方；积的乘方', 2),
    ('10.\nA. a^2·a^3=a^5\nB. a^3+a^3=a^6\nC. a^8÷a^4=a^4\nD. (a^3)^3=a^6', 'D', 'A', '学生误选 D：D 错误（(a^3)^3=a^9 而非 a^6）；正确答案 A（a^2·a^3=a^5）', '同底数幂的除法；幂的乘方', 2),
    ('11. 若 10^a=3, 10^b=2, 则 10^(2a-b)=?', '9/2', '9/2', '', '幂的运算（含字母指数）', 3),
    ('12. 在长为 3a+2、宽为 2b-1 的长方形铁片上，挖去长为 2a+4、宽为 b 的小长方形铁片，则剩余部分面积是（ ）\nA. 6ab-3a+4b\nB. 4ab-3a-2\nC. 6ab-3a+8b-2\nD. 4ab-3a+8b-2', 'B', 'B', '', '多项式乘多项式；面积公式', 3),
    ('13. 关于 x 的代数式 (3-ax)(3+2x) 的化简结果中不含 x 的一次项，则 a 的值是（ ）\nA. 1\nB. 2\nC. 3\nD. 4', 'D', 'B', '学生误选 D：(3-ax)(3+2x)=9+(6-3a)x-2ax^2，令 6-3a=0，a=2，故正确答案为 B（a=2）', '多项式乘多项式；合并同类项', 3),
    ('14.\nA. (a-1)^2=a^2-1\nB. (-a^2b)^2=-a^4b^2\nC. a^6+a^3=a^3\nD. (a^2)^3=a^6', 'D', 'D', '', '完全平方公式；积的乘方；幂的乘方', 3),
    ('15.\nA. 3a+a^2=3a^3\nB. (-3a^3)^2=6a^6\nC. a^2·a^3=a^6\nD. (a-b)^2=a^2-2ab+b^2', 'C', 'D', '学生误选 C：C 错误（a^2·a^3=a^5 而非 a^6）；正确答案为 D（(a-b)^2=a^2-2ab+b^2）', '完全平方公式；合并同类项；幂的运算', 3),
    ('16.\nA. (-a)^2=-a^2\nB. 2a^2-a^2=a^2\nC. a^2·a=a^3\nD. (a+1)^2=a^2+1', 'C', 'B、C（多选）', 'A 错（应为 a^2）；D 错（应为 a^2+2a+1）；B、C 均正确', '完全平方公式；幂的乘方', 3),
]

for timu, sda, zda, cwf, zd, diff in qs:
    execute_db(
        'INSERT INTO mistake_records (uuid,sys_platform,xueke,timu,xueshengdaan,zhengquedaan,cuowufenxi,zhishidian,difficulty,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (uuid, 'web', '数学', timu, sda, zda, cwf, zd, diff, 'active'))

print(f'重导 {len(qs)} 条完成，uuid={uuid[:16]}...')
for r in query_db('SELECT id, substr(timu,1,50) t FROM mistake_records WHERE id>=55 ORDER BY id'):
    print(f"  #{r['id']} {r['t']}")
