#include "esp_camera.h"
#include "img_converters.h"   
#include <ESP32Servo.h>
#include "Base64.h"

/* ---------- AI-Thinker pin map ---------- */
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     36
#define Y5_GPIO_NUM     21
#define Y4_GPIO_NUM     19
#define Y3_GPIO_NUM     18
#define Y2_GPIO_NUM      5
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22
/* --------------------------------------- */

#define SERVO_PIN 14
Servo tapServo;

/* ROI fractions (same numbers the Python used) */
constexpr float ROI_TOP_FRAC    = 0.25f;
constexpr float ROI_BOTTOM_FRAC = 1.00f;
constexpr float ROI_LEFT_FRAC   = 0.15f;
constexpr float ROI_RIGHT_FRAC  = 0.75f;

/* Throw away the first N frames in the FIFO */
static void discard_stale_frames(uint8_t n)
{
  for (uint8_t i = 0; i < n; ++i) {
    camera_fb_t *tmp = esp_camera_fb_get();
    if (!tmp) break;
    esp_camera_fb_return(tmp);
  }
}

void smoothMove(int fromDeg, int toDeg) {
  const int dir = (toDeg > fromDeg) ? 1 : -1;
  for (int a = fromDeg; a != toDeg; a += dir) {
    tapServo.write(a);
    delay(5);
  }
  tapServo.write(toDeg);              
}

void pressSkip()
{
  smoothMove(0, 38);                   
  delay(350);                        
  smoothMove(38, 0); 
}

void setup()
{
  Serial.begin(460800);
  delay(2000);

  /* ---------- Servo ---------- */
  tapServo.setPeriodHertz(50);
  tapServo.attach(SERVO_PIN, 500, 2400); 
  tapServo.write(5);              

  /* ---------- Camera config ---------- */
  camera_config_t config{};
  config.ledc_channel   = LEDC_CHANNEL_0;
  config.ledc_timer     = LEDC_TIMER_0;
  config.pin_d0         = Y2_GPIO_NUM;
  config.pin_d1         = Y3_GPIO_NUM;
  config.pin_d2         = Y4_GPIO_NUM;
  config.pin_d3         = Y5_GPIO_NUM;
  config.pin_d4         = Y6_GPIO_NUM;
  config.pin_d5         = Y7_GPIO_NUM;
  config.pin_d6         = Y8_GPIO_NUM;
  config.pin_d7         = Y9_GPIO_NUM;
  config.pin_xclk       = XCLK_GPIO_NUM;
  config.pin_pclk       = PCLK_GPIO_NUM;
  config.pin_vsync      = VSYNC_GPIO_NUM;
  config.pin_href       = HREF_GPIO_NUM;
  config.pin_sccb_sda   = SIOD_GPIO_NUM;
  config.pin_sccb_scl   = SIOC_GPIO_NUM;
  config.pin_pwdn       = PWDN_GPIO_NUM;
  config.pin_reset      = RESET_GPIO_NUM;
  config.xclk_freq_hz   = 20000000;
  config.pixel_format   = PIXFORMAT_GRAYSCALE;  
  config.frame_size     = FRAMESIZE_VGA;       
  config.jpeg_quality   = 12;                
  config.fb_count       = 2;                   
  config.grab_mode      = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed");
    for (;;) delay(1000);
  }

  /* Discard power-on garbage */
  discard_stale_frames(5);

  sensor_t *s = esp_camera_sensor_get();
  s->set_brightness(s, 1);
  s->set_contrast  (s, 1);
  s->set_vflip     (s, 1);
  s->set_hmirror   (s, 1);

  tapServo.write(0);       
  Serial.println("Init complete");
  Serial.println("READY");  
}

void loop()
{
  if (!Serial.available()) { delay(5); return; }

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  while (Serial.available()) Serial.read();  // flush extra chars

  /* ---------- Capture ---------- */
  if (cmd == "CAPTURE") {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Capture failed");
      Serial.println("READY");
      return;
    }

    /* ---- Crop loot strip into its own buffer ------------------------ */
    const uint16_t W = fb->width;
    const uint16_t H = fb->height;
    const uint16_t x0     = W * ROI_LEFT_FRAC;
    const uint16_t y0     = H * ROI_TOP_FRAC;
    const uint16_t roi_w  = W * (ROI_RIGHT_FRAC  - ROI_LEFT_FRAC);
    const uint16_t roi_h  = H * (ROI_BOTTOM_FRAC - ROI_TOP_FRAC);

    uint8_t *roi = (uint8_t*)malloc(roi_w * roi_h);
    if (!roi) {
      esp_camera_fb_return(fb);
      Serial.println("ROI malloc failed");
      Serial.println("READY");
      return;
    }

    for (uint16_t r = 0; r < roi_h; ++r)
      memcpy(roi + r * roi_w,
             fb->buf + (y0 + r) * W + x0,
             roi_w);

    esp_camera_fb_return(fb);  

    /* ---- JPEG encode the ROI --------------------------------------- */
    uint8_t *jpg  = nullptr;
    size_t   jlen = 0;
    if (!fmt2jpg(roi, roi_w * roi_h, roi_w, roi_h,
                 PIXFORMAT_GRAYSCALE, 12, &jpg, &jlen)) {
      free(roi);
      Serial.println("ROI JPEG encode failed");
      Serial.println("READY");
      return;
    }
    free(roi);

    /* ---- Base-64 stream -------------------------------------------- */
    String b64 = base64::encode(jpg, jlen);
    free(jpg);

    Serial.println("-----START-IMAGE-----");
    for (size_t i = 0; i < b64.length(); i += 512)
      Serial.println(b64.substring(i, i + 512));
    Serial.println("-----END-IMAGE-----");

    Serial.flush();           
    Serial.println("READY");     
  }

  /* ---------- Servo skip ---------- */
  else if (cmd == "SKIP") {
    pressSkip();
    Serial.println("READY");
  }
}