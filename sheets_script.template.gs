/**
 * EduApp Instagram-бот → Google Sheets.
 * Бот әр адамның жауабын осы скриптке жібереді; скрипт оны бір жолға жазады
 * (A бағанындағы ID бойынша: бар болса — жаңартады, жоқ болса — жаңа жол қосады).
 * Ештеңені өзгертпеңіз, тек Deploy жасаңыз.
 */
const SECRET = "__SECRET__";
const HEADERS = ["ID (бот үшін)", "Бірінші жазған уақыты", "Instagram", "Бағыт", "Қала", "Сынып", "Телефон",
                 "Жауаптары (толық)", "Рақмет жіберілді", "Соңғы жаңарту"];

function doPost(e) {
  const reply = (obj) => ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (err) { return reply({ ok: false, error: "bad json" }); }
  if (d.secret !== SECRET) return reply({ ok: false, error: "forbidden" });

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    if (sheet.getLastRow() === 0) sheet.appendRow(HEADERS);
    const ids = sheet.getRange(1, 1, sheet.getLastRow(), 1).getValues().map(r => String(r[0]));
    const values = [String(d.id), d.first, d.instagram, d.topic, d.city, d.grade, d.phone, d.texts, d.thanked, d.updated];
    let row = ids.indexOf(String(d.id)) + 1;
    if (row < 2) row = sheet.getLastRow() + 1;
    // Телефон мен сынып мәтін ретінде сақталсын (0 жоғалмасын, күнге айналмасын).
    sheet.getRange(row, 6, 1, 2).setNumberFormat("@");
    sheet.getRange(row, 1, 1, values.length).setValues([values]);
    return reply({ ok: true, row: row });
  } finally {
    lock.releaseLock();
  }
}

/** Қолмен тексеру үшін: Apps Script-те осы функцияны іске қосыңыз — кестеде «TEST» жолы пайда болады. */
function testWrite() {
  const e = { postData: { contents: JSON.stringify({ secret: SECRET, id: "TEST", first: "", instagram: "@test", topic: "Тест",
    city: "Астана", grade: "5", phone: "+7 700 000 00 00", texts: "тест жол — өшіре беріңіз", thanked: "", updated: "" }) } };
  Logger.log(doPost(e).getContent());
}
