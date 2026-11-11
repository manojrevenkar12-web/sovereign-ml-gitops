-- Redaction engine. Lua 5.1 / LuaJIT, so the same file runs inside Fluent Bit and, through lupa, in
-- the ML pipeline. RULES is prepended by scripts/gen_redactor.py from config/pii_rules.yaml.

local M = {}

local function digits_only(s)
  return (s:gsub("%D", ""))
end

local function mod97(numstr)
  local r = 0
  for i = 1, #numstr do
    r = (r * 10 + tonumber(numstr:sub(i, i))) % 97
  end
  return r
end

-- IBAN (DE): "DE" + 2 check digits + 18 digits, single spaces allowed between digits.
local function iban_end(text, s)
  local i, count, last = s + 4, 0, s + 3
  while i <= #text and count < 18 do
    local c = text:sub(i, i)
    if c:match("%d") then
      count, last, i = count + 1, i, i + 1
    elseif c == " " and text:sub(i + 1, i + 1):match("%d") then
      i = i + 1
    else
      break
    end
  end
  if count ~= 18 or text:sub(last + 1, last + 1):match("%d") then
    return nil
  end
  local raw = digits_only(text:sub(s + 2, last))
  if mod97(raw:sub(3) .. "1314" .. raw:sub(1, 2)) ~= 1 then
    return nil
  end
  return last
end

local validators = {}

function validators.steuerid(m)
  if m:sub(1, 1) == "0" then return false end
  local counts, multi = {}, 0
  for i = 1, 10 do
    local d = m:sub(i, i)
    counts[d] = (counts[d] or 0) + 1
  end
  for _, c in pairs(counts) do
    if c > 3 then return false end
    if c >= 2 then multi = multi + 1 end
  end
  if multi ~= 1 then return false end
  local product = 10
  for i = 1, 10 do
    local s = (tonumber(m:sub(i, i)) + product) % 10
    if s == 0 then s = 10 end
    product = (s * 2) % 11
  end
  local check = 11 - product
  if check == 10 then check = 0 end
  return check == tonumber(m:sub(11, 11))
end

function validators.ipv4(m)
  for octet in m:gmatch("%d+") do
    if tonumber(octet) > 255 then return false end
  end
  return true
end

function validators.phone(m)
  local n = #digits_only(m:gsub("%%2[0B]", " "))
  return n >= 9 and n <= 15
end

local function overlaps(spans, s, e)
  for _, sp in ipairs(spans) do
    if s <= sp[3] and e >= sp[2] then return true end
  end
  return false
end

local function has_context(lower, s, words, window)
  local from = s - window
  if from < 1 then from = 1 end
  local before = lower:sub(from, s - 1)
  for _, w in ipairs(words) do
    if before:find(w, 1, true) then return true end
  end
  return false
end

local function escape(p)
  return (p:gsub("[%^%$%(%)%%%.%[%]%*%+%-%?]", "%%%0"))
end

local CAP = "[%u\195\196\197][%a\128-\255%-]*"

-- Returns the spans {kind, first byte, last byte} found in text, ordered by position.
function M.detect(text)
  local spans = {}
  local lower = text:lower()
  for _, rule in ipairs(RULES) do
    for _, pat in ipairs(rule.patterns or {}) do
      local init = 1
      while init <= #text do
        local s, e = text:find(pat, init)
        if not s then break end
        local ok = true
        if rule.validator == "iban" then
          local last = iban_end(text, s)
          if last then e = last else ok = false end
        elseif rule.validator then
          ok = validators[rule.validator](text:sub(s, e))
        end
        if ok and rule.context then
          ok = has_context(lower, s, rule.context, rule.context_window or 24)
        end
        if ok and not overlaps(spans, s, e) then
          spans[#spans + 1] = {rule.kind, s, e}
          init = e + 1
        else
          init = s + 1
        end
      end
    end
    for _, ctx in ipairs(rule.after or {}) do
      local init = 1
      while true do
        local s, e = lower:find(ctx, init, true)
        if not s then break end
        local ts, te = text:find("^" .. CAP, e + 1)
        if ts then
          local last, n = te, 1
          while n < (rule.tokens or 1) do
            local s2, e2 = text:find("^ " .. CAP, last + 1)
            if not s2 then break end
            last, n = e2, n + 1
          end
          if not overlaps(spans, ts, last) then
            spans[#spans + 1] = {rule.kind, ts, last}
          end
        end
        init = e + 1
      end
    end
    if rule.gazetteer then
      rule.set = rule.set or {}
      for _, w in ipairs(rule.gazetteer) do rule.set[w] = true end
      for s, word, e in text:gmatch("()([%a\128-\255]+)()") do
        if rule.set[word:lower()] then
          local last = e - 1
          if rule.surname then
            local s2, e2 = text:find("^ " .. CAP, e)
            if s2 then last = e2 end
          end
          if not overlaps(spans, s, last) then
            spans[#spans + 1] = {rule.kind, s, last}
          end
        end
      end
    end
    for _, pre in ipairs(rule.prefixes or {}) do
      local pat = "%f[%a]" .. escape(pre) .. "[%a\128-\255%-]+ %d+%a?%f[^%w]"
      local init = 1
      while true do
        local s, e = lower:find(pat, init)
        if not s then break end
        if not overlaps(spans, s, e) then
          spans[#spans + 1] = {rule.kind, s, e}
        end
        init = e + 1
      end
    end
    for _, suf in ipairs(rule.suffixes or {}) do
      local pat = "[%a\128-\255%-]*" .. escape(suf) .. " %d+%a?"
      local init = 1
      while true do
        local s, e = text:find(pat, init)
        if not s then break end
        if not overlaps(spans, s, e) then
          spans[#spans + 1] = {rule.kind, s, e}
        end
        init = e + 1
      end
    end
  end
  table.sort(spans, function(a, b) return a[2] < b[2] end)
  return spans
end

-- Returns the redacted text and the spans that were replaced.
function M.redact(text)
  local spans = M.detect(text)
  if #spans == 0 then return text, spans end
  local parts, pos = {}, 1
  for _, sp in ipairs(spans) do
    parts[#parts + 1] = text:sub(pos, sp[2] - 1)
    parts[#parts + 1] = (PLACEHOLDER:gsub("{kind}", sp[1]))
    pos = sp[3] + 1
  end
  parts[#parts + 1] = text:sub(pos)
  return table.concat(parts), spans
end

local function walk(v)
  if type(v) == "string" then
    local out, spans = M.redact(v)
    return out, #spans
  elseif type(v) == "table" then
    local total = 0
    for k, x in pairs(v) do
      local out, n = walk(x)
      v[k] = out
      total = total + n
    end
    return v, total
  end
  return v, 0
end

-- Fluent Bit filter entry point (call = redact_record). Adds pii_redactions so Loki can alert the
-- team whose service logs personal data, without storing the data itself.
function redact_record(tag, timestamp, record)
  local out, n = walk(record)
  if n == 0 then return 0, timestamp, record end
  out["pii_redactions"] = n
  return 2, timestamp, out
end

REDACTOR = M
return M
