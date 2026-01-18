-- Estate Carousel Filter for Quarto
-- Creates a Bootstrap carousel with angled image cards and descriptive content

local carousel_count = 0
local css_added = false

-- Ensure CSS dependency is added
local function ensureHtmlDeps()
  if not css_added then
    quarto.doc.add_html_dependency({
      name = 'estate-carousel',
      version = '1.0.0',
      stylesheets = {'estate-carousel.css'}
    })
    css_added = true
  end
end

-- Helper function to generate a unique ID
local function get_carousel_id()
  carousel_count = carousel_count + 1
  return "estate-carousel-" .. carousel_count
end

-- Helper function to parse parameters string "Key: Value | Key2: Value2"
local function parse_params(params_str)
  if not params_str or params_str == "" then
    return {}
  end

  local params = {}
  for pair in string.gmatch(params_str, "[^|]+") do
    local key, value = string.match(pair, "^%s*(.-)%s*:%s*(.-)%s*$")
    if key and value then
      table.insert(params, {key = key, value = value})
    end
  end
  return params
end

-- Process a single estate item
local function process_estate(div, index, total, carousel_id)
  local name = div.attributes["name"] or "Untitled"
  local blurb = div.attributes["blurb"] or ""
  local image = div.attributes["image"] or ""
  local params_str = div.attributes["params"] or ""
  local params = parse_params(params_str)

  -- Get the content (description) from the div
  local content = pandoc.write(pandoc.Pandoc(div.content), "html")

  -- Build parameters HTML
  local params_html = ""
  if #params > 0 then
    params_html = '<div class="estate-params">'
    for i, p in ipairs(params) do
      params_html = params_html .. '<span class="estate-param"><span class="estate-param-key">' .. p.key .. ':</span> <span class="estate-param-value">' .. p.value .. '</span></span>'
      if i < #params then
        params_html = params_html .. '<span class="estate-param-sep"></span>'
      end
    end
    params_html = params_html .. '</div>'
  end

  -- Build image HTML
  local image_html = ""
  if image ~= "" then
    image_html = '<img src="' .. image .. '" alt="' .. name .. '" class="estate-card-img">'
  else
    image_html = '<div class="estate-card-placeholder"></div>'
  end

  -- Determine if this is the active slide
  local active_class = ""
  if index == 1 then
    active_class = " active"
  end

  -- Build the carousel item HTML
  local html = string.format([[
<div class="carousel-item%s" data-bs-interval="false">
  <div class="estate-item">
    <div class="estate-card-container">
      <div class="estate-card">
        %s
      </div>
    </div>
    <div class="estate-content">
      <h3 class="estate-name">%s</h3>
      <p class="estate-blurb">%s</p>
      <div class="estate-description">%s</div>
      %s
    </div>
  </div>
</div>]], active_class, image_html, name, blurb, content, params_html)

  return html
end

-- Main filter function for Div elements
function Div(div)
  -- Check if this is an estate-carousel
  if div.classes:includes("estate-carousel") then
    if not quarto.doc.is_format("html") then
      return div
    end

    -- Add CSS dependency
    ensureHtmlDeps()

    local carousel_id = get_carousel_id()
    local items_html = ""

    -- Find all estate items within the carousel
    local estates = {}
    for _, block in ipairs(div.content) do
      if block.t == "Div" and block.classes:includes("estate") then
        table.insert(estates, block)
      end
    end

    -- Process each estate item
    for i, estate in ipairs(estates) do
      items_html = items_html .. process_estate(estate, i, #estates, carousel_id)
    end

    -- Build the complete carousel HTML
    local carousel_html = string.format([[
<div class="estate-carousel-wrapper">
  <hr class="estate-carousel-border">
  <div id="%s" class="carousel slide estate-carousel" data-bs-ride="false">
    <div class="carousel-inner">
      %s
    </div>
    <button class="carousel-control-prev" type="button" data-bs-target="#%s" data-bs-slide="prev">
      <span class="carousel-control-prev-icon" aria-hidden="true"></span>
      <span class="visually-hidden">Previous</span>
    </button>
    <button class="carousel-control-next" type="button" data-bs-target="#%s" data-bs-slide="next">
      <span class="carousel-control-next-icon" aria-hidden="true"></span>
      <span class="visually-hidden">Next</span>
    </button>
  </div>
  <hr class="estate-carousel-border">
</div>]], carousel_id, items_html, carousel_id, carousel_id)

    return pandoc.RawBlock("html", carousel_html)
  end

  return div
end
