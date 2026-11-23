import json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

_CNW = {"creationflags": subprocess.CREATE_NO_WINDOW}

def _base_dir():
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent

def _scripts_dir():
    d = Path.home() / ".jarvis" / "reminders"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _sanitise(text, max_len=200):
    return text.replace("\\", "").replace('"', "").replace("'", "").replace("\n", " ").replace("\r", "").strip()[:max_len]

def _write_notify_script(task_name, message):
    script_path = _scripts_dir() / f"{task_name}.py"
    msg_literal = json.dumps(message)
    notify_block = "if \n        notify_block = f\"\"\"\nmessage = {msg_literal}\nnotified = False\n\ntry:\n    from plyer import notification\n    notification.notify(title=\"J.A.R.V.I.S Reminder\", message=message, timeout=15)\n    notified = True\nexcept Exception:\n    pass\n\nif not notified:\n    try:\n        from win10toast import ToastNotifier\n        ToastNotifier().show_toast(\"J.A.R.V.I.S Reminder\", message, duration=15, threaded=False)\n        notified = True\n    except Exception:\n        pass\n\nif not notified:\n    try:\n        import subprocess\n        subprocess.run([\"msg\", \"*\", \"/TIME:30\", message], check=False)\n    except Exception:\n        pass\n\ntry:\n    import winsound\n    for freq in [800, 1000, 1200]:\n        winsound.Beep(freq, 180)\n        import time; time.sleep(0.08)\nexcept Exception:\n    pass\n\"\"\"\n"
    script_body = f"""# Auto-generated reminder script
import pathlib
{notify_block}
try:
    pathlib.Path(__file__).unlink(missing_ok=True)
except Exception:
    pass
"""
    script_path.write_text(script_body, encoding="utf-8")
    script_path.chmod(0o600)
    return script_path

def _schedule_windows(target_dt: datetime, task_name: str,
                     script_path: Path, message: str) -> str:
    python_exe = Path(sys.executable)
    pythonw = python_exe.parent / "pythonw.exe"
    if pythonw.exists():
        python_exe = pythonw

    xml_path = _scripts_dir() / f"{task_name}.xml"
    xml_content = (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        '  <RegistrationInfo><Description>J.A.R.V.I.S Reminder</Description></RegistrationInfo>\n'
        '  <Triggers><TimeTrigger>\n'
        f'    <StartBoundary>{target_dt.strftime("%Y-%m-%dT%H:%M:%S")}</StartBoundary>\n'
        '    <Enabled>true</Enabled>\n'
        '  </TimeTrigger></Triggers>\n'
        '  <Actions><Exec>\n'
        f'    <Command>{python_exe}</Command>\n'
        f'    <Arguments>"{script_path}"</Arguments>\n'
        '  </Exec></Actions>\n'
        '  <Settings>\n'
        '    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>\n'
        '    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n'
        '    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n'
        '    <StartWhenAvailable>true</StartWhenAvailable>\n'
        '    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>\n'
        '    <Enabled>true</Enabled>\n'
        '  </Settings>\n'
        '  <Principals><Principal>\n'
        '    <LogonType>InteractiveToken</LogonType>\n'
        '    <RunLevel>LeastPrivilege</RunLevel>\n'
        '  </Principal></Principals>\n'
        '</Task>'
    )

    xml_path.write_text(xml_content, encoding="utf-16")

    result = subprocess.run(
        ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_path), "/F"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", **_CNW,
    )

    try:
        xml_path.unlink(missing_ok=True)
    except Exception:
        pass

    if result.returncode != 0:
        script_path.unlink(missing_ok=True)
        err = (result.stderr or result.stdout).strip()
        print(f"[Reminder] ❌ schtasks: {err}")
        return ""  

    return task_name




def reminder(parameters, response=None, player=None, session_memory=None):
    date_str = parameters.get("date", "").strip()
    time_str = parameters.get("time", "").strip()
    message = parameters.get("message", "Reminder").strip()
    if not date_str or not time_str:
        return "I need both a date and a time to set a reminder."
    try:
        target_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return "I couldn't parse that date or time. Please use YYYY-MM-DD and HH:MM."
    if target_dt <= datetime.now():
        return "That time has already passed — I can't set a reminder in the past."
    safe_msg = _sanitise(message)
    task_name = f"JARVISReminder_{target_dt.strftime('%Y%m%d_%H%M%S')}"
    phone = _mirror_to_cloud(message, target_dt)
    phone += _add_spoken_routine(message, target_dt)
    try:
        script_path = _write_notify_script(task_name, safe_msg)
    except Exception as e:
        return f"Could not prepare the reminder script: {e}{phone}"
    try:
        job_id = _schedule_windows(target_dt, task_name, script_path, safe_msg)
    except Exception as e:
        script_path.unlink(missing_ok=True)
        print(f"[Reminder] Scheduling exception: {e}")
        return f"Something went wrong while scheduling the reminder.{phone}"
    if not job_id:
        return f"I couldn't register the reminder with Windows Task Scheduler.{phone}"
    if player:
        player.write_log(f"[Reminder] {date_str} {time_str} — {safe_msg[:40]}")
    return f"Reminder set for {target_dt.strftime('%B %d at %I:%M %p')}.{phone}"

def _add_spoken_routine(message, target_dt):
    try:
        from core.routines import desktop
        eng = desktop.engine()
        if eng is None:
            return ""
        eng.add(name=message[:60] or "Reminder", kind="say", text=message,
                trigger={"type":"time", "rule":{"type":"once","at_ts":target_dt.timestamp()}},
                source="reminder")
        return " It will also be said aloud at that time while the assistant is running."
    except Exception as e:
        print(f"[Reminder] spoken copy not set: {e}")
        return ""

def _mirror_to_cloud(message, target_dt):
    try:
        from memory.config_manager import get_plugin_config, get_plugin_enabled
        if not (str(get_plugin_config("cloud_agent").get("pair_code") or "").strip()
                and get_plugin_enabled("cloud_agent")):
            return ""
        agent = sys.modules.get("plugins.cloud_agent")
        if agent is None or not hasattr(agent, "mirror_reminder"):
            return ""
        ok, detail = agent.mirror_reminder(message, target_dt.strftime("%Y-%m-%d %H:%M"))
    except Exception as e:
        ok, detail = False, str(e)
    if ok:
        return " It will also be sent to the user's phone over Telegram at that time."
    return f" The phone copy could not be set ({detail}) — only this computer will remind them."

TOOL = {
    "name":"reminder",
    "description":"Sets a timed Windows reminder using Task Scheduler.",
    "parameters":{"type":"OBJECT","properties":{
        "date":{"type":"STRING","description":"Date in YYYY-MM-DD format"},
        "time":{"type":"STRING","description":"Time in HH:MM format (24h)"},
        "message":{"type":"STRING","description":"Reminder message text"}},
        "required":["date","time","message"]},
    "handler":reminder,
}
