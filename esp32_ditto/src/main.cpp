#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

// ---- 板载资源，完全不需要额外接线 ----
#define BOOT_BTN   0     // 板上自带的 BOOT 按键，当"触发异常"的模拟按钮
#define RGB_PIN    38    // 板上自带的可寻址 RGB LED（图上标注 RGB@IO38）

Adafruit_NeoPixel rgb(1, RGB_PIN, NEO_GRB + NEO_KHZ800);

bool lastBtnState = HIGH;
unsigned long lastPressTime = 0;
const unsigned long DEBOUNCE_MS = 250;

// 几条不同的"警报"话术，按下按键时随机挑一条发给电脑朗读
const char* alerts[] = {
  "ALERT:客厅摄像头正在向境外陌生地址上传数据，我已经把它隔离了。",
  "ALERT:扫地机器人的麦克风被异常唤醒，检测到未授权访问。",
  "ALERT:智能门锁收到暴力破解尝试，已自动锁定并断网。"
};
const int alertCount = 3;

void setIdleColor(){
  rgb.setPixelColor(0, rgb.Color(10, 6, 20)); // 极暗的紫色，呼应 Ditto 配色，代表"待机守护中"
  rgb.show();
}

void flashAlert(){
  for(int i=0;i<3;i++){
    rgb.setPixelColor(0, rgb.Color(255, 20, 40)); // 警报红
    rgb.show();
    delay(120);
    rgb.setPixelColor(0, rgb.Color(0,0,0));
    rgb.show();
    delay(100);
  }
  setIdleColor();
}

void setup() {
  Serial.begin(115200);
  pinMode(BOOT_BTN, INPUT_PULLUP); // BOOT 按键按下时为低电平

  rgb.begin();
  rgb.setBrightness(60);
  setIdleColor();

  delay(500);
  Serial.println("READY:Ditto 已上线，正在守护中...");
}

void loop() {
  bool btnState = digitalRead(BOOT_BTN);

  // 检测到按键从"未按"变成"按下"，且过了防抖时间
  if (btnState == LOW && lastBtnState == HIGH &&
      millis() - lastPressTime > DEBOUNCE_MS) {
    lastPressTime = millis();

    int idx = random(0, alertCount);
    Serial.println(alerts[idx]); // 通过串口把警报文字发给 Mac，由 Mac 念出来
    flashAlert();
  }

  lastBtnState = btnState;
  delay(20);
}
