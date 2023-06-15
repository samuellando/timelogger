export function durationToString(millis: number, recur = 0) {
  let d = millis;
  let m = 1;
  let s = "millis";

  const SECOUND = 1000;
  const MINUTE = 60 * SECOUND;
  const HOUR = 60 * MINUTE;
  const DAY = 24 * HOUR;

  if (d >= DAY) {
    d = Math.floor(d / DAY);
    m = DAY;
    s = 'day' + ((d > 1) ? "s" : "");
  } else if (d >= HOUR) {
    d = Math.floor(d / HOUR);
    m = HOUR;
    s = 'hour' + ((d > 1) ? "s" : "");
  } else if (d >= MINUTE) {
    d = Math.floor(d / MINUTE);
    m = MINUTE;
    s = 'min' + ((d > 1) ? "s" : "");
  } else if (d >= SECOUND) {
    d = Math.floor(d / SECOUND);
    m = SECOUND;
    s = 'sec' + ((d > 1) ? "s" : "");
  }

  let r = "";
  if (d != 0) {
    r += d + " " + s;
  }
  if (recur > 0) {
    r += " " + durationToString(millis - d * m)
  }

  return r;
}

export function toDateTimeString(now: Date) {
  let month = '' + (now.getMonth() + 1);
  let day = '' + now.getDate();
  let year = now.getFullYear();

  if (month.length < 2) month = '0' + month;
  if (day.length < 2) day = '0' + day;

  return [year, month, day].join('-') + 'T' + now.toLocaleTimeString();
}
