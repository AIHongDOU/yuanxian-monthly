import hashlib
import json
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import make_msgid
from ledger import require
from book import shift

TO = ("330520199@qq.com","185365235@qq.com")

def digest(data):
    return hashlib.sha256(data).hexdigest()

def deliver(address, data, sender):
    host=os.environ["YX_SMTP_HOST"]
    password=os.environ["YX_SMTP_PASSWORD"]
    if not sender:
        return "失败","未配置 YX_SMTP_USER"
    try:
        client=smtplib.SMTP_SSL(host,int(os.getenv("YX_SMTP_PORT","465")),timeout=30,context=ssl.create_default_context())
    except (OSError,smtplib.SMTPException) as e:
        return "失败",f"连接失败：{e}"
    try:
        try:
            client.login(sender,password)
        except (OSError,smtplib.SMTPException) as e:
            return "失败",f"认证失败：{e}"
        try:
            refused=client.sendmail(sender,[address],data)
            return ("失败",str(refused[address][0])) if refused else ("已接受","SMTP 服务器已接受")
        except (smtplib.SMTPRecipientsRefused,smtplib.SMTPResponseException) as e:
            return "失败",str(e)
        except (OSError,smtplib.SMTPServerDisconnected) as e:
            return "待查",str(e)
    finally:
        client.close()

def process(req,state,path,folder,profile,month,save,transport=deliver):
    require(path.exists() and state.get("final_sha"),"请先定稿")
    attachment=path.read_bytes()
    fingerprint=digest(attachment)
    require(fingerprint==state["final_sha"],"定稿文件校验失败，须核对附件")
    sender=os.getenv("YX_SMTP_USER","")
    subject=f"{profile['name']}{int(month[-2:])}月月度报表"
    msg=EmailMessage(policy=SMTP)
    msg["To"]=", ".join(TO)
    if sender: msg["From"]=sender
    msg["Subject"]=subject
    msg["Message-ID"]=make_msgid()
    msg.set_content(f"您好，附件包含 {month} 工作总结和 {shift(month,1)} 工作计划，请查收。")
    msg.add_attachment(attachment,maintype="application",subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",filename=path.name)
    mail=state.setdefault("mail",{})
    delivery=mail.setdefault("投递",{})
    draft=folder/"月报邮件.eml"
    summary={"收件人":TO,"主题":subject,"附件":path.name,"发件账号":sender,"投递":delivery,"邮件草稿":str(draft)}
    if req["action"]=="preview":
        draft.write_bytes(msg.as_bytes())
        mail.update(token=secrets.token_hex(16),draft_hash=digest(draft.read_bytes()),sender=sender)
        save()
        return dict(summary,确认码=mail["token"])
    if req["action"]=="reconcile":
        addr=req["address"]
        require(addr in TO and delivery.get(addr,{}).get("状态")=="待查" and req["status"] in ("失败","已接受") and req.get("evidence"),"需核对发件记录，再登记该地址结果及依据")
        delivery[addr]={"状态":req["status"],"说明":req["evidence"]}
        mail.pop("token",None)
        save()
        return summary
    token=mail.get("token")
    require(token and secrets.compare_digest(token,req.get("confirm","")),"需要用户确认最新预览")
    data=draft.read_bytes()
    require(mail["sender"]==sender and mail["draft_hash"]==digest(data),"邮件或账号已变更，请重新预览")
    del mail["token"]
    save()
    for addr in TO:
        if delivery.get(addr,{}).get("状态") in ("已接受","待查"): continue
        delivery[addr]={"状态":"待查","说明":"投递中断时请核对发件服务记录"}
        save()
        try:
            status,detail=transport(addr,data,sender)
        except (KeyError,ValueError,smtplib.SMTPAuthenticationError,smtplib.SMTPConnectError) as e:
            status,detail="失败",str(e)
        except OSError as e:
            status,detail="待查",str(e)
        delivery[addr]={"状态":status,"说明":detail}
        save()
    return summary

