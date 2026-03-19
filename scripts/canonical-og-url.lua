-- Canonical URL and og:url injector for all Quarto pages
-- Adds <link rel="canonical"> and <meta property="og:url"> to every page

function Meta(meta)
  local site_url = meta['site-url'] and pandoc.utils.stringify(meta['site-url']) or nil
  if not site_url then return meta end

  -- Remove trailing slash
  site_url = site_url:gsub("/$", "")

  -- Get the input file to derive the page path
  local input_file = PANDOC_STATE.input_files[1]
  if not input_file then return meta end

  -- Make path relative (remove leading ./)
  input_file = input_file:gsub("^%./", "")

  -- Convert source extension to .html
  local path = input_file:gsub("%.qmd$", ".html"):gsub("%.md$", ".html")

  -- index.html -> directory URL (clean URLs)
  path = path:gsub("index%.html$", "")

  -- Ensure starts with /
  if not path:match("^/") then
    path = "/" .. path
  end

  local canonical_url = site_url .. path

  -- Inject canonical link and og:url meta
  local html = '<link rel="canonical" href="' .. canonical_url .. '">\n'
  html = html .. '<meta property="og:url" content="' .. canonical_url .. '">'

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
