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

local function format_date(d)
  if d == nil then return nil end
  local s = pandoc.utils.stringify(d)
  -- If already ISO format, return as-is
  if s:match("^%d%d%d%d%-%d%d%-%d%d") then
    return s:sub(1, 10)
  end
  return s
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

  -- Build categories/keywords array
  local keywords = {}
  if meta.categories then
    for _, cat in ipairs(meta.categories) do
      table.insert(keywords, '"' .. escape_json_string(pandoc.utils.stringify(cat)) .. '"')
    end
  end

  -- Build the image URL
  local image_url = ""
  if image then
    -- For relative image paths, we can't know the full URL at build time
    -- but we provide what we can
    image_url = escape_json_string(image)
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
  json = json .. ',"headline":"' .. escape_json_string(title) .. '"'
  json = json .. ',"description":"' .. escape_json_string(description) .. '"'

  if date then
    json = json .. ',"datePublished":"' .. escape_json_string(date) .. '"'
    json = json .. ',"dateModified":"' .. escape_json_string(date) .. '"'
  end

  json = json .. ',"author":{"@type":"Person"'
  json = json .. ',"name":"Chris von Csefalvay"'
  json = json .. ',"url":"https://chrisvoncsefalvay.com"'
  json = json .. ',"sameAs":["https://orcid.org/0000-0003-3131-0864","https://scholar.google.com/citations?user=X_2G-VsAAAAJ","https://github.com/chrisvoncsefalvay","https://www.linkedin.com/in/chrisvoncsefalvay/"]'
  json = json .. '}'

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
    json = json .. ',"sameAs":"https://doi.org/' .. escape_json_string(doi) .. '"'
  end

  json = json .. ',"inLanguage":"en"'
  json = json .. ',"mainEntityOfPage":{"@type":"WebPage","@id":"https://chrisvoncsefalvay.com"}'

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
