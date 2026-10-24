// A small Server-Sent Events parser for fetch streams (EventSource cannot POST).
// Feed it decoded text as it arrives; it calls onEvent once per complete event.
// Handles events split across reads, several events in one read, ": ping" comments and CRLF or CR line ends.

export type SseEvent = { event: string; data: string };

export function sseParser(onEvent: (e: SseEvent) => void) {
  let buffer = "";
  let event = "";
  let data: string[] = [];

  function line(text: string) {
    if (text === "") {
      if (data.length) onEvent({ event: event || "message", data: data.join("\n") });
      event = "";
      data = [];
      return;
    }
    if (text.startsWith(":")) return; // a comment, such as the keep-alive ping
    const colon = text.indexOf(":");
    const field = colon < 0 ? text : text.slice(0, colon);
    let value = colon < 0 ? "" : text.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }

  return {
    push(text: string) {
      buffer += text;
      // A CR at the very end may be the first half of a CRLF, so it waits for the next read.
      const lineEnd = /\r\n|\n|\r(?=[^\n])/g;
      let from = 0;
      for (let m = lineEnd.exec(buffer); m; m = lineEnd.exec(buffer)) {
        line(buffer.slice(from, m.index));
        from = m.index + m[0].length;
      }
      buffer = buffer.slice(from);
    },
    // The stream ended: a last event without its blank line is still delivered.
    end() {
      const rest = buffer.replace(/\r$/, "");
      buffer = "";
      if (rest) line(rest);
      line("");
    },
  };
}
