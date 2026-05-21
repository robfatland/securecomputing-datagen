-- Pandoc Lua filter: replace emoji with text equivalents for PDF output
-- Source markdown stays unchanged; this only affects pandoc rendering.
function Str(elem)
  elem.text = elem.text:gsub("\xF0\x9F\x93\x8B", "[NOTE]")      -- 📋
  elem.text = elem.text:gsub("\xE2\x9C\x85", "[YES]")            -- ✅
  elem.text = elem.text:gsub("\xE2\x9D\x8C", "[NO]")             -- ❌
  elem.text = elem.text:gsub("\xF0\x9F\x94\x84", "[CYCLE]")      -- 🔄
  elem.text = elem.text:gsub("\xE2\x9A\xA0", "[WARNING]")        -- ⚠
  elem.text = elem.text:gsub("\xEF\xB8\x8F", "")                 -- U+FE0F variation selector
  return elem
end
