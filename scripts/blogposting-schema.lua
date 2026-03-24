-- BlogPosting JSON-LD schema generator for Quarto blog posts
-- Injects structured data into the <head> of each blog post

local function escape_json_string(s)
  if s == nil then return "" end
  s = s:gsub('\\', '\\\\')
  s = s:gsub('"', '\\"')
  s = s:gsub('\n', '\\n')
  s = s:gsub('\r', '\\r')
  s = s:gsub('\t', '\\t')
  return s
end

local months = {
  january = "01", february = "02", march = "03", april = "04",
  may = "05", june = "06", july = "07", august = "08",
  september = "09", october = "10", november = "11", december = "12"
}

local function format_date(d)
  if d == nil then return nil end
  local s = pandoc.utils.stringify(d)
  -- If already ISO format, return as-is
  if s:match("^%d%d%d%d%-%d%d%-%d%d") then
    return s:sub(1, 10)
  end
  -- Parse "30 October 2023" or "6 July 2025"
  local day, mon, year = s:match("^(%d+)%s+(%a+)%s+(%d%d%d%d)$")
  if day and mon and year then
    local m = months[mon:lower()]
    if m then
      return string.format("%s-%s-%02d", year, m, tonumber(day))
    end
  end
  -- Parse "October 30, 2023"
  local mon2, day2, year2 = s:match("^(%a+)%s+(%d+),?%s+(%d%d%d%d)$")
  if mon2 and day2 and year2 then
    local m = months[mon2:lower()]
    if m then
      return string.format("%s-%s-%02d", year2, m, tonumber(day2))
    end
  end
  return s
end

local SITE_URL = "https://chrisvoncsefalvay.com"

local function get_page_url(meta)
  -- Try to get site-url from Quarto's website config
  local site_url = nil
  if meta.website and type(meta.website) == "table" and meta.website['site-url'] then
    site_url = pandoc.utils.stringify(meta.website['site-url'])
  elseif meta['site-url'] then
    site_url = pandoc.utils.stringify(meta['site-url'])
  end
  if not site_url then
    site_url = SITE_URL
  end
  site_url = site_url:gsub("/$", "")

  -- Get the real source file path (not Quarto's temp path)
  local input_file = nil
  local project_dir = nil

  if quarto and quarto.doc and quarto.doc.input_file then
    input_file = quarto.doc.input_file
  end
  if quarto and quarto.project and quarto.project.directory then
    project_dir = quarto.project.directory
  end

  -- Fall back to PANDOC_STATE.input_files
  if not input_file then
    input_file = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  end

  if not input_file then return site_url end

  -- Make path relative to project directory
  if project_dir then
    project_dir = project_dir:gsub("/$", "")
    local escaped = project_dir:gsub("([%.%+%-%*%?%[%]%^%$%(%)%%])", "%%%1")
    input_file = input_file:gsub("^" .. escaped .. "/?", "")
  end

  -- Reject temp paths (Quarto renders via /tmp/quarto-session...)
  if input_file:match("quarto%-session") or input_file:match("quarto%-input") then
    return site_url
  end

  input_file = input_file:gsub("^%./", "")
  local path = input_file:gsub("%.qmd$", "/"):gsub("%.md$", "/")
  path = path:gsub("index/$", "")
  if path == "" then path = "/" end
  if not path:match("^/") then path = "/" .. path end
  return site_url .. path
end

function Meta(meta)
  -- Only apply to documents that look like blog posts (have date + title + categories)
  if not meta.title or not meta.date or not meta.categories then
    return meta
  end

  local title = pandoc.utils.stringify(meta.title)
  local date = format_date(meta.date)
  local description = meta.description and pandoc.utils.stringify(meta.description) or ""
  local image = meta.image and pandoc.utils.stringify(meta.image) or nil
  local page_url = get_page_url(meta)

  -- Build categories/keywords array
  local keywords = {}
  if meta.categories then
    for _, cat in ipairs(meta.categories) do
      table.insert(keywords, '"' .. escape_json_string(pandoc.utils.stringify(cat)) .. '"')
    end
  end

  -- Build the image URL (make fully qualified if relative)
  local image_url = ""
  if image then
    if image:match("^https?://") then
      image_url = escape_json_string(image)
    elseif page_url then
      -- Ensure no double slash when joining
      local base = page_url:gsub("/$", "")
      image_url = escape_json_string(base .. "/" .. image:gsub("^/", ""))
    else
      image_url = escape_json_string(image)
    end
  end

  -- Extract DOI if present
  local doi = nil
  if meta.citation then
    if type(meta.citation) == "table" and meta.citation.doi then
      doi = pandoc.utils.stringify(meta.citation.doi)
    end
  end

  -- Build JSON-LD
  local json = '{"@context":"https://schema.org"'
  json = json .. ',"@type":"BlogPosting"'
  json = json .. ',"@id":"' .. escape_json_string(page_url) .. '#article"'
  json = json .. ',"headline":"' .. escape_json_string(title) .. '"'
  json = json .. ',"description":"' .. escape_json_string(description) .. '"'
  json = json .. ',"url":"' .. escape_json_string(page_url) .. '"'

  if date then
    json = json .. ',"datePublished":"' .. escape_json_string(date) .. '"'
    json = json .. ',"dateModified":"' .. escape_json_string(date) .. '"'
  end

  json = json .. ',"author":{"@id":"https://chrisvoncsefalvay.com/#person"}'

  json = json .. ',"publisher":{"@type":"Person"'
  json = json .. ',"name":"Chris von Csefalvay"'
  json = json .. ',"url":"https://chrisvoncsefalvay.com"'
  json = json .. ',"image":{"@type":"ImageObject","url":"https://chrisvoncsefalvay.com/img/portrait_2x3midres.webp"}'
  json = json .. '}'

  if image_url ~= "" then
    json = json .. ',"image":"' .. image_url .. '"'
  end

  if #keywords > 0 then
    json = json .. ',"keywords":[' .. table.concat(keywords, ',') .. ']'
  end

  if doi then
    json = json .. ',"sameAs":["https://doi.org/' .. escape_json_string(doi) .. '"]'
  end

  json = json .. ',"inLanguage":"en"'
  json = json .. ',"isPartOf":{"@id":"https://chrisvoncsefalvay.com/#website"}'
  json = json .. ',"mainEntityOfPage":{"@type":"WebPage","@id":"' .. escape_json_string(page_url) .. '"}'

  -- Add speakable specification
  json = json .. ',"speakable":{"@type":"SpeakableSpecification","cssSelector":["article h1",".description","article > section > p:first-of-type"]}'

  json = json .. '}'

  -- Inject into the HTML head via Pandoc's header-includes
  local script = '<script type="application/ld+json">' .. json .. '</script>'

  local header_includes = meta['header-includes']
  if header_includes == nil then
    header_includes = pandoc.MetaList({})
  elseif header_includes.t ~= "MetaList" then
    header_includes = pandoc.MetaList({header_includes})
  end

  header_includes:insert(pandoc.MetaBlocks({pandoc.RawBlock('html', script)}))
  meta['header-includes'] = header_includes

  return meta
end
