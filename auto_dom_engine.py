# -*- coding: utf-8 -*-
import time, random
from selenium.webdriver.common.by import By
from human_behavior import HumanAction
from form_gate import safe_get, ensure_register_form


def dismiss_popups(driver):
    """Tự động tìm và tắt các popup thông báo, quảng cáo, xin quyền"""
    try:
        js_script = """
        function closePopups() {
            // 1. Tìm các nút có chữ Hủy, Đóng, Đồng ý, X
            let keywords = ['hủy', 'huỷ', 'đóng', 'đồng ý', 'ok', 'xác nhận', 'cho phép'];
            let els = document.querySelectorAll('button, div, span, a');
            for (let e of els) {
                let txt = (e.innerText || '').trim().toLowerCase();
                if (keywords.includes(txt) && e.offsetWidth > 0) {
                    e.click();
                }
            }
            // 2. Xóa các lớp overlay che màn hình
            let overlays = document.querySelectorAll('.modal-backdrop, .overlay, .ant-modal-mask, .van-overlay');
            overlays.forEach(o => o.remove());
            return true;
        }
        return closePopups();
        """
        driver.execute_script(js_script)
    except:
        pass

def run_full_flow(driver, url, game, item, results, doctor):
    try:
        print(f"🧑‍💻 Bắt đầu: {item.get('full_name')} | {game}...")
        safe_get(driver, url)
        ensure_register_form(driver)
        time.sleep(2)
        dismiss_popups(driver)
        
        if doctor:
            doctor.snapshot(driver, "page_loaded")
            try:
                print(f"🧠 Đang kích hoạt AI Doctor học form: {game}")
                doctor.learn_form_structure(driver)
            except Exception as exc:
                print(
                    f"⚠️ AI Doctor học form thất bại: "
                    f"{type(exc).__name__}: {exc}"
                )

        pass_val = "12345678qq"
        
        js_fill = """
        const userVal = arguments[0], passVal = arguments[1], nameVal = arguments[2], phoneNoZero = arguments[3], bankAcc = arguments[4];
        let filled = [];
        function setVal(el, val, fieldName) {
            if (!el || !val) return false;
            try {
                el.focus();
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                if (setter) setter.call(el, val); else el.value = val;
                el.dispatchEvent(new Event('input', { bubbles: true })); 
                el.dispatchEvent(new Event('change', { bubbles: true }));
                filled.push(fieldName);
                return true;
            } catch(e) { return false; }
        }
        Array.from(document.querySelectorAll('input')).filter(i => i.getBoundingClientRect().width > 40 && !['checkbox', 'hidden', 'submit'].includes(i.type)).forEach((inp) => {
            let h = (inp.name + ' ' + inp.id + ' ' + inp.placeholder).toLowerCase();
            if (inp.type === 'password' || h.includes('pass') || h.includes('mật khẩu')) { setVal(inp, passVal, 'password'); }
            else if (h.includes('tên') || h.includes('fullname') || h.includes('realname')) { setVal(inp, nameVal, 'fullname'); }
            else if (h.includes('điện thoại') || h.includes('phone') || h.includes('tel') || h.includes('sđt')) { setVal(inp, phoneNoZero, 'phone'); }
            else if (h.includes('ngân hàng') || h.includes('stk') || h.includes('bank')) { setVal(inp, bankAcc, 'bank'); }
            else if (h.includes('tài khoản') || h.includes('account') || h.includes('user') || h.includes('login')) { setVal(inp, userVal, 'username'); }
        });
        document.querySelectorAll('input[type="checkbox"]').forEach(cb => { 
            let h = (cb.name + ' ' + cb.id + ' ' + cb.className).toLowerCase();
            if ((h.includes('term') || h.includes('agree') || h.includes('điều khoản') || h.includes('đồng ý')) && !cb.checked) cb.click(); 
        });
        return filled;
        """
        
    
        import random
        time.sleep(random.uniform(1.5, 3.0)) # Human-like Delay truoc khi dien form
        filled = []
        try: filled = driver.execute_script(js_fill, item['username'], pass_val, item['full_name'], item['phone_no_zero'], item['bank_acc']) or []
        except: pass
        
        print(f"🧑‍💻 Đã điền: {filled}")
            
        if "username" not in filled or "password" not in filled:
            print("🧑‍💻 Dùng AI Doctor tìm ô nhập...")
            try:
                el = doctor.find(driver, "username_input", fallback="input[name='username']")
                if el: HumanAction.human_type(driver, el, item['username'])
                el = doctor.find(driver, "password_input", fallback="input[type='password']")
                if el: HumanAction.human_type(driver, el, pass_val)
            except Exception as e: print(f"⚠️ AI Doctor: {e}")
            
        # Chế độ duyệt thủ công: dừng tuyệt đối trước thao tác gửi biểu mẫu.
        # Người dùng kiểm tra dữ liệu và tự quyết định có bấm nút trên trình duyệt hay không.
        time.sleep(1)
        if doctor:
            try:
                doctor.snapshot(driver, "manual_review")
            except Exception:
                pass
        print("🖐️ Đã điền biểu mẫu. Đang chờ người dùng kiểm tra và thao tác thủ công.")
        return "MANUAL_REVIEW"
        
    except Exception as e:
        # BẮT LỖI ALERT TOÀN DIỆN
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"🚨 Web chặn bằng Alert: {alert_text}")
            alert.accept()
            return "LOCKED"
        except:
            # Không phải Alert, hoặc không tìm thấy Alert -> Văng lỗi ra ngoài
            print(f"❌ Lỗi hệ thống Selenium: {e}")
            return "FAILED"
