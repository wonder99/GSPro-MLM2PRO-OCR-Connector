import cv2
import numpy as np
from PIL import Image
from ctypes import windll
import win32gui
import win32ui
import matplotlib.pyplot as plt

w = -1
h = -1

def capture_window(window_name: str, target_width: int, target_height: int) -> np.array:
    global w, h
    windll.user32.SetProcessDPIAware()
    hwnd = win32gui.FindWindow(None, window_name)
    if not hwnd:
        raise RuntimeError(f"Can't find window called '{window_name}'")
    
    rect = win32gui.GetClientRect(hwnd)
    if w == -1 :
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
    else :
        if not (w == rect[2] - rect[0] and h == rect[3] - rect[0]) :
            raise RuntimeError(f"Target window ({window_name}) size has changed to {w}x{h} {rect}")

    if not (w==target_width and h==target_height) :
        print(f"dimensions seem wrong {w}x{h} vs json:{target_width}x{target_height}")

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bitmap)

    result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)

    bmpinfo = bitmap.GetInfo()
    bmpstr = bitmap.GetBitmapBits(True)

    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4))
    img = np.ascontiguousarray(img)[..., :-1] 

    if not result:  
        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        raise RuntimeError(f"Unable to acquire screenshot! Result: {result}")

    return img

def process_screenshot(screenshot, api, rois):
    example = Image.fromarray(cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)).convert('L')
    result = {}

    for name, roi in rois.items():
        cropValue = example.crop(roi)
        
        # Convert to binary
        cropValue_np = np.array(cropValue)
        _, binary_cropValue = cv2.threshold(cropValue_np, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        # Morphological operation to remove smaller text elements
        kernel = np.ones((5,5),np.uint8)
        binary_cropValue = cv2.morphologyEx(binary_cropValue, cv2.MORPH_OPEN, kernel)

        # Convert binary image back to PIL Image
        binary_cropValue_pil = Image.fromarray(binary_cropValue)

        api.SetImage(binary_cropValue_pil)
        raw_value = api.GetUTF8Text()

        # Ignore non-numeric characters
        cleaned_value = ''.join(c for c in raw_value if c.isdigit() or c == '.' or c == '-')

        # strip any trailing periods, which can sometimes come from degree symbols
        value = cleaned_value.strip('.') if cleaned_value else '0'

        result[name] = value

    return result
