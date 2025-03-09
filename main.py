import cv2
import numpy as np
from directkeys import PressKey, ReleaseKey, E, One
import time
import win32gui
import win32con
from mss import mss
import logging
from os import system

# Hata günlüğü (log) ayarları
logging.basicConfig(
    level=logging.ERROR,  # Yalnızca hata mesajlarını kaydet
    format='%(asctime)s - %(levelname)s - %(message)s',  # Zaman damgası, seviye ve mesaj formatı
    handlers=[
        logging.FileHandler('error.log'),  # Hataları error.log dosyasına kaydet
        logging.StreamHandler()  # Hataları konsola da yazdır
    ]
)

def get_active_window_title():
    try:
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    except Exception as e:
        logging.error(f"Pencere başlığı alınırken hata oluştu: {e}")
        return ""

def bring_cmd_to_front():
    try:
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    except Exception as e:
        logging.error(f"Komut istemi öne getirilirken hata oluştu: {e}")

def detect_fishing_bar():
    bring_cmd_to_front()
    try:
        # Şablon görüntülerini yükle
        template_green = cv2.imread("templates/green_box.jpg", 0)
        template_white = cv2.imread("templates/white_box.jpg", 0)
        
        if template_green is None or template_white is None:
            error_msg = "HATA: Şablon görüntüleri yüklenemedi! Lütfen 'templates' klasöründe 'green_box.jpg' ve 'white_box.jpg' dosyalarının olduğundan emin olun."
            print(error_msg)
            logging.error(error_msg)
            return
        
        with mss() as sct:
            last_state = None
            last_message = None
            green_box = None
            white_was_detected = False  # Beyaz kutunun önceki çerçevede tespit edilip edilmediğini izlemek için
            
            while True:
                # Window check
                if "FiveM" not in get_active_window_title():
                    if last_message != "FiveM inactive":
                        print("FiveM açık değil, bekleniyor...")
                        last_message = "FiveM inactive"
                    time.sleep(1)
                    continue
                
                try:
                    # Ekran görüntüsünü al
                    screenshot = sct.grab(sct.monitors[1])
                    frame = np.array(screenshot)
                    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                except Exception as e:
                    logging.error(f"Ekran görüntüsü alınırken hata oluştu: {e}")
                    continue
                
                # Yeşil kutuyu tespit et
                try:
                    green_detected = False
                    res_green = cv2.matchTemplate(frame_gray, template_green, cv2.TM_CCOEFF_NORMED)
                    _, max_val_green, _, max_loc_green = cv2.minMaxLoc(res_green)
                    
                    if max_val_green > 0.8:
                        green_box = {
                            'x': max_loc_green[0],
                            'y': max_loc_green[1],
                            'w': template_green.shape[1],
                            'h': template_green.shape[0]
                        }
                        green_detected = True
                        
                        # Yeşil kutunun bulunduğu bölgede beyaz kutuyu ara
                        roi = frame_gray[green_box['y']:green_box['y']+green_box['h'], 
                                       0:green_box['x']+green_box['w']]  # Beyaz kutu barın solundan başlar
                        res_white = cv2.matchTemplate(roi, template_white, cv2.TM_CCOEFF_NORMED)
                        _, max_val_white, _, max_loc_white = cv2.minMaxLoc(res_white)
                        
                        # Beyaz kutuyu ekran koordinatlarına çevir
                        white_x = max_loc_white[0]
                        white_y = green_box['y'] + max_loc_white[1]
                        white_detected = max_val_white > 0.9

                        if white_detected:
                            white_box = {
                                'x': white_x,
                                'y': white_y,
                                'w': template_white.shape[1],
                                'h': template_white.shape[0]
                            }
                    else:
                        white_detected = False
                        green_box = None
                except Exception as e:
                    logging.error(f"Kutu tespiti sırasında hata oluştu: {e}")
                    continue

                # Durum yönetimi
                current_state = None
                if green_detected:
                    if white_detected:
                        current_state = "white_detected"
                        white_was_detected = True  # Beyaz kutu tespit edildi, bunu hatırla
                        if last_state != current_state:
                            print("Beyaz kutu tespit edildi, hareket izleniyor...")
                    elif white_was_detected:  # Beyaz kutu kayboldu ve yeşil kutu hala varsa
                        current_state = "white_disappeared"
                        if last_state != current_state:
                            print("Beyaz kutu kayboldu! 'e' ve '1' tuşlarına basılıyor...")
                            try:
                                PressKey(E)
                                time.sleep(0.1)
                                ReleaseKey(E)
                                time.sleep(0.3)
                                PressKey(One)
                                time.sleep(0.1)
                                ReleaseKey(One)
                            except Exception as e:
                                logging.error(f"Tuş basma işlemi sırasında hata oluştu: {e}")
                            white_was_detected = False  # Beyaz kutu kayboldu, durumu sıfırla
                            last_message = "action_taken"
                    else:
                        current_state = "green_only"
                else:
                    current_state = "not_detected"
                    white_was_detected = False  # Beyaz kutu kayboldu, durumu sıfırla

                # Durum değişikliklerinde mesaj güncelle
                if current_state != last_state:
                    if current_state == "white_detected":
                        pass  # Zaten işlendi
                    elif current_state == "white_disappeared":
                        pass  # Zaten işlendi
                    elif current_state == "green_only":
                        print("Yeşil kutu tespit edildi ancak beyaz kutu bulunamadı!")
                    else:
                        print("Balık tutma ekranı bekleniyor...")
                    
                    last_state = current_state
                    last_message = current_state

                # 30 FPS için uyku süresi (yaklaşık 1/30 saniye)
                time.sleep(1/30)

    except Exception as e:
        logging.error(f"detect_fishing_bar fonksiyonunda genel bir hata oluştu: {e}")

if __name__ == "__main__":
    try:
        detect_fishing_bar()
    except Exception as e:
        logging.error(f"Program çalıştırılırken genel bir hata oluştu: {e}")