-- Canonical URL, og:url, and og:type injector for all Quarto pages
-- Adds <link rel="canonical">, <meta property="og:url">, and <meta property="og:type">

local SITE_URL = "https://chrisvoncsefalvay.com"

local function get_site_url(meta)
  -- Quarto nests site-url under website in _quarto.yml
  if meta.website and type(meta.website) == "table" and meta.website['site-url'] then
    return pandoc.utils.stringify(meta.website['site-url'])
  end
  if meta['site-url'] then
    return pandoc.utils.stringify(meta['site-url'])
  end
  return SITE_URL
end

local function get_page_path()
  -- Strategy 1: Use Quarto's API (gives real source path, not temp file)
  local input_file = nil
  local project_dir = nil

  if quarto and quarto.doc and quarto.doc.input_file then
    input_file = quarto.doc.input_file
  end
  if quarto and quarto.project and quarto.project.directory then
    project_dir = quarto.project.directory
  end

  -- Strategy 2: Fall back to PANDOC_STATE.input_files
  if not input_file then
    input_file = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  end

  if not input_file then return "/" end

  -- If we have a project directory, make the path relative
  if project_dir then
    -- Ensure project_dir ends without slash for consistent stripping
    project_dir = project_dir:gsub("/$", "")
    local escaped = project_dir:gsub("([%.%+%-%*%?%[%]%^%$%(%)%%])", "%%%1")
    input_file = input_file:gsub("^" .. escaped .. "/?", "")
  end

  -- Reject temp paths (Quarto renders via /tmp/quarto-session.../quarto-input...)
  if input_file:match("quarto%-session") or input_file:match("quarto%-input") then
    return nil
  end

  -- Clean up and convert to URL path
  input_file = input_file:gsub("^%./", "")
  local path = input_file:gsub("%.qmd$", "/"):gsub("%.md$", "/")
  path = path:gsub("index/$", "")
  if path == "" then path = "/" end
  if not path:match("^/") then path = "/" .. path end

  return path
end

function Meta(meta)
  local site_url = get_site_url(meta):gsub("/$", "")
  local page_path = get_page_path()

  -- If we couldn't determine the page path, skip injection
  if not page_path then return meta end

  local canonical_url = site_url .. page_path

  -- Determine og:type: "article" for blog posts, "website" for everything else
  local og_type = "website"
  if meta.date and meta.categories then
    og_type = "article"
  end

  -- Build HTML to inject
  local html = '<link rel="canonical" href="' .. canonical_url .. '">\n'
  html = html .. '<meta property="og:url" content="' .. canonical_url .. '">\n'
  html = html .. '<meta property="og:type" content="' .. og_type .. '">'

  local header_includes = meta['header-includes']
  if header_includes == nil then
    header_includes = pandoc.MetaList({})
  elseif header_includes.t ~= "MetaList" then
    header_includes = pandoc.MetaList({header_includes})
  end

  header_includes:insert(pandoc.MetaBlocks({pandoc.RawBlock('html', html)}))
  meta['header-includes'] = header_includes

  return meta
end
