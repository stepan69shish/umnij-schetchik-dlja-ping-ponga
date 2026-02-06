import cv2
import numpy as np
import time
import smbus2

# ================================
# КОНФИГУРАЦИЯ
# ================================

# --- Настройки LCD через I2C ---
I2C_ADDR = 0x27  # Адрес LCD
I2C_BUS = 1      # Номер шины I2C

# --- Настройки камеры ---
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# --- Цветовые границы для оранжевого в HSV ---
LOWER_ORANGE = np.array([5, 100, 100])    # Нижняя граница оранжевого
UPPER_ORANGE = np.array([15, 255, 255])   # Верхняя граница оранжевого

# --- Пороги игры ---
BOTTOM_THRESHOLD = 400        # Зона засчета очка
POINT_DELAY_THRESHOLD = 1.5   # Время в зоне для засчета очка
POINT_DELAY = 2               # Пауза между очками
RESTART_DELAY = 5             # Пауза перед перезапуском игры
MAX_SCORE = 11                # Победный счет

# ================================
# LCD КЛАСС (ОПТИМИЗИРОВАННЫЙ)
# ================================

class LCDDisplay:
    def __init__(self, i2c_addr=0x27, i2c_bus=1):
        self.i2c_addr = i2c_addr
        self.available = False
        self.bus = None
        
        # Команды LCD
        self.LCD_BACKLIGHT = 0x08
        self.LCD_ENABLE = 0x04
        self.LCD_CHR = 1
        self.LCD_CMD = 0
        self.LCD_LINES = [0x80, 0xC0, 0x94, 0xD4]
        
        try:
            self.bus = smbus2.SMBus(i2c_bus)
            self.available = True
            self._initialize()
            print("LCD: Инициализация успешна")
        except Exception as e:
            print(f"LCD: Ошибка инициализации - {e}")
    
    def _initialize(self):
        """Инициализация LCD"""
        if not self.available:
            return
            
        init_sequence = [0x33, 0x32, 0x06, 0x0C, 0x28, 0x01]
        for cmd in init_sequence:
            self._send_byte(cmd, self.LCD_CMD)
            time.sleep(0.0005)
    
    def _send_byte(self, bits, mode):
        """Отправка байта на LCD"""
        if not self.available:
            return
            
        bits_high = mode | (bits & 0xF0) | self.LCD_BACKLIGHT
        bits_low = mode | ((bits << 4) & 0xF0) | self.LCD_BACKLIGHT
        
        try:
            self.bus.write_byte(self.i2c_addr, bits_high)
            self._toggle_enable(bits_high)
            self.bus.write_byte(self.i2c_addr, bits_low)
            self._toggle_enable(bits_low)
        except Exception:
            pass
    
    def _toggle_enable(self, bits):
        """Переключение бита Enable"""
        if not self.available:
            return
            
        try:
            self.bus.write_byte(self.i2c_addr, (bits | self.LCD_ENABLE))
            time.sleep(0.0005)
            self.bus.write_byte(self.i2c_addr, (bits & ~self.LCD_ENABLE))
            time.sleep(0.0005)
        except Exception:
            pass
    
    def display_text(self, line1="", line2=""):
        """Вывод текста на LCD"""
        if not self.available:
            return
            
        line1 = line1.ljust(16)[:16]
        line2 = line2.ljust(16)[:16]
        
        self._send_byte(self.LCD_LINES[0], self.LCD_CMD)
        for char in line1:
            self._send_byte(ord(char), self.LCD_CHR)
            
        self._send_byte(self.LCD_LINES[1], self.LCD_CMD)
        for char in line2:
            self._send_byte(ord(char), self.LCD_CHR)
    
    def clear(self):
        """Очистка LCD"""
        if self.available:
            self._send_byte(0x01, self.LCD_CMD)

# ================================
# КЛАСС ИГРЫ ПИНГ-ПОНГ
# ================================

class PingPongGame:
    def __init__(self):
        self.left_score = 0
        self.right_score = 0
        self.game_active = True
        self.point_paused = False
        self.point_start_time = None
        self.point_timers = {"left": None, "right": None}
        self.restart_timer = None
        
    def award_point(self, player):
        """Засчитать очко игроку"""
        if player == "left":
            self.left_score += 1
            print(f"[SCORE] Левый игрок: {self.left_score}-{self.right_score}")
        else:
            self.right_score += 1
            print(f"[SCORE] Правый игрок: {self.left_score}-{self.right_score}")
        
        # Проверка победы
        if self._check_winner():
            self.game_active = False
            self.restart_timer = time.time()
        
        # Пауза перед следующим розыгрышем
        self.point_paused = True
        self.point_start_time = time.time()
    
    def _check_winner(self):
        """Проверка условий победы"""
        if (self.left_score >= MAX_SCORE and 
            self.left_score - self.right_score >= 2):
            print(f"🎉 Левый игрок победил! {self.left_score}-{self.right_score}")
            return True
        elif (self.right_score >= MAX_SCORE and 
              self.right_score - self.left_score >= 2):
            print(f"🎉 Правый игрок победил! {self.left_score}-{self.right_score}")
            return True
        return False
    
    def check_restart(self):
        """Проверка необходимости перезапуска игры"""
        if not self.game_active and self.restart_timer:
            if time.time() - self.restart_timer >= RESTART_DELAY:
                self._restart_game()
                return True
        return False
    
    def _restart_game(self):
        """Перезапуск игры"""
        print("[GAME] Перезапуск игры!")
        self.left_score = 0
        self.right_score = 0
        self.game_active = True
        self.point_paused = False
        self.point_start_time = None
        self.point_timers = {"left": None, "right": None}
        self.restart_timer = None
    
    def update_point_timer(self, current_time):
        """Обновление паузы между очками"""
        if self.point_paused and current_time - self.point_start_time >= POINT_DELAY:
            self.point_paused = False
            self.point_timers = {"left": None, "right": None}
            print("[GAME] Новый розыгрыш!")
            return True
        return False
    
    def get_game_status(self):
        """Получить текущий статус игры"""
        if not self.game_active:
            return "GAME_OVER"
        elif self.point_paused:
            return "POINT_PAUSED"
        else:
            return "PLAYING"
    
    def get_lcd_status(self):
        """Получить текст для LCD"""
        score_text = f"L:{self.left_score:02d} - R:{self.right_score:02d}"
        
        if not self.game_active:
            if self.left_score > self.right_score:
                status_text = "LEFT PLAYER WON!"
            else:
                status_text = "RIGHT PLAYER WON!"
        elif self.point_paused:
            status_text = "POINT PAUSED"
        else:
            status_text = "GAME ACTIVE"
            
        return score_text, status_text

# ================================
# ОСНОВНАЯ ПРОГРАММА
# ================================

def process_side(frame, side_name, start_x, end_x, game, lcd):
    """Обработка одной половины поля"""
    height, width = frame.shape[:2]
    mid_x = width // 2
    
    half = frame[:, start_x:end_x].copy()
    hsv = cv2.cvtColor(half, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, LOWER_ORANGE, UPPER_ORANGE)
    
    # Морфологические операции для улучшения качества
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    current_time = time.time()
    
    if contours:
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        
        if area > 300:  # Минимальная площадь объекта
            M = cv2.moments(largest)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"]) + start_x
                cy = int(M["m01"] / M["m00"])
                
                # Визуализация объекта
                contour_adjusted = largest + [start_x, 0]
                cv2.drawContours(frame, [contour_adjusted], -1, (0, 165, 255), 2)  # Оранжевый контур
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)  # Красная точка центра
                
                # Отображение информации
                cv2.putText(frame, f"{side_name}: TRACKING", (start_x + 10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                
                # Логика засчета очка
                if game.game_active and not game.point_paused and cy > BOTTOM_THRESHOLD:
                    if game.point_timers[side_name.lower()] is None:
                        game.point_timers[side_name.lower()] = current_time
                        print(f"[TIMER] Таймер запущен для {side_name}")
                    
                    elapsed = current_time - game.point_timers[side_name.lower()]
                    
                    # Отображение оставшегося времени
                    cv2.putText(frame, f"TIME: {POINT_DELAY_THRESHOLD - elapsed:.1f}s", 
                               (start_x + 10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    
                    # Проверка достижения порога
                    if elapsed >= POINT_DELAY_THRESHOLD:
                        # Засчитать очко противоположному игроку
                        if side_name == "LEFT":
                            game.award_point("right")
                        else:
                            game.award_point("left")
                else:
                    # Сброс таймера если объект вышел из зоны
                    if game.point_timers[side_name.lower()] is not None:
                        print(f"[TIMER] Таймер сброшен для {side_name}")
                        game.point_timers[side_name.lower()] = None
                        
            return True
    
    # Если объект не обнаружен
    cv2.putText(frame, f"{side_name}: NO OBJECT", (start_x + 10, 60), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    game.point_timers[side_name.lower()] = None
    
    return False

def draw_game_overlay(frame, game, width, height):
    """Отрисовка интерфейса игры"""
    mid_x = width // 2
    
    # Разделительная линия
    cv2.line(frame, (mid_x, 0), (mid_x, height), (255, 255, 255), 2)
    
    # Линия засчета очка
    cv2.line(frame, (0, BOTTOM_THRESHOLD), (width, BOTTOM_THRESHOLD), (0, 0, 255), 2)
    cv2.putText(frame, "POINT ZONE", (10, BOTTOM_THRESHOLD - 10), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    
    # Счет
    cv2.putText(frame, f"LEFT: {game.left_score}", (10, height - 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
    cv2.putText(frame, f"RIGHT: {game.right_score}", (mid_x + 10, height - 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
    
    # Статус игры
    if not game.game_active:
        winner = "LEFT" if game.left_score > game.right_score else "RIGHT"
        restart_time = RESTART_DELAY - (time.time() - game.restart_timer)
        cv2.putText(frame, f"GAME OVER! {winner} WINS!", (150, 200), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
        cv2.putText(frame, f"RESTART IN: {restart_time:.1f}s", (200, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    elif game.point_paused:
        remaining = POINT_DELAY - (time.time() - game.point_start_time)
        cv2.putText(frame, f"NEXT POINT IN: {remaining:.1f}s", 
                   (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

def main():
    # Инициализация LCD
    lcd = LCDDisplay(I2C_ADDR, I2C_BUS)
    
    # Инициализация камеры
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    
    if not cap.isOpened():
        print("Ошибка: Не удалось открыть камеру")
        return
    
    # Создание игры
    game = PingPongGame()
    
    # Переменные для оптимизации
    last_lcd_update = 0
    LCD_UPDATE_INTERVAL = 0.5
    
    print("🎮 Игра в пинг-понг запущена! Нажмите 'q' для выхода.")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            current_time = time.time()
            height, width = frame.shape[:2]
            
            # Обновление состояния игры
            game.update_point_timer(current_time)
            game.check_restart()
            
            # Обновление LCD (периодическое)
            if current_time - last_lcd_update > LCD_UPDATE_INTERVAL:
                score_text, status_text = game.get_lcd_status()
                lcd.display_text(score_text, status_text)
                last_lcd_update = current_time
            
            # Обработка обеих половин поля
            for side_name, start_x, end_x in [("LEFT", 0, width//2), ("RIGHT", width//2, width)]:
                process_side(frame, side_name, start_x, end_x, game, lcd)
            
            # Отрисовка интерфейса
            draw_game_overlay(frame, game, width, height)
            
            # Отображение кадра
            cv2.imshow("Ping Pong Tracking", frame)
            
            # Выход по 'q'
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
                
    finally:
        # Завершение работы
        cap.release()
        cv2.destroyAllWindows()
        lcd.display_text("GAME FINISHED", f"SCORE: {game.left_score}-{game.right_score}")
        time.sleep(2)
        lcd.clear()
        print(f"🎯 Финальный счет: {game.left_score} - {game.right_score}")

if __name__ == "__main__":
    main()

