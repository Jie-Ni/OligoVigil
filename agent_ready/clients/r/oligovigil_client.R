oligovigil_url <- function(base_url, path, params = list()) {
  params <- params[!vapply(params, function(value) is.null(value) || identical(value, ""), logical(1))]
  query <- if (length(params)) paste0("?", paste(names(params), utils::URLencode(unlist(params)), sep = "=", collapse = "&")) else ""
  paste0(sub("/$", "", base_url), path, query)
}

oligovigil_json <- function(base_url, path, params = list()) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Install jsonlite before using the OligoVigil R client.")
  }
  jsonlite::fromJSON(oligovigil_url(base_url, path, params), simplifyVector = FALSE)
}

oligovigil_search <- function(query, limit = 20, base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(base_url, "/api/search", list(q = query, limit = limit))
}

oligovigil_evidence_records <- function(domain = "", query = "", limit = 100, base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(base_url, "/api/evidence_records", list(domain = domain, q = query, limit = limit))
}

oligovigil_evidence_detail <- function(domain, evidence_id, base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(base_url, "/api/evidence_detail", list(domain = domain, id = evidence_id))
}

oligovigil_safety_dossier <- function(sequence = "", helm = "", target = "", modification = "", delivery = "",
                                      endpoint = "", species = "", base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(
    base_url,
    "/api/safety_dossier",
    list(
      sequence = sequence,
      helm = helm,
      target = target,
      modification = modification,
      delivery = delivery,
      endpoint = endpoint,
      species = species
    )
  )
}

oligovigil_evidence_graph <- function(sequence = "", helm = "", target = "", modification = "", delivery = "",
                                      endpoint = "", species = "", base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(
    base_url,
    "/api/evidence_graph",
    list(
      sequence = sequence,
      helm = helm,
      target = target,
      modification = modification,
      delivery = delivery,
      endpoint = endpoint,
      species = species
    )
  )
}

oligovigil_benchmark <- function(base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(base_url, "/api/benchmark")
}

oligovigil_download_manifest <- function(base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(base_url, "/api/download_manifest")
}

oligovigil_offtarget_taxonomy <- function(base_url = "https://oligovigil.pages.dev") {
  oligovigil_json(base_url, "/api/offtarget_taxonomy")
}

oligovigil_evidence_release <- function(base_url = "https://oligovigil.pages.dev") {
  utils::read.csv(oligovigil_url(base_url, "/api/download/evidence_release.csv"), stringsAsFactors = FALSE)
}

oligovigil_benchmark_splits <- function(base_url = "https://oligovigil.pages.dev") {
  utils::read.csv(oligovigil_url(base_url, "/api/download/benchmark_reference_splits.csv"), stringsAsFactors = FALSE)
}

oligovigil_benchmark_baselines <- function(base_url = "https://oligovigil.pages.dev") {
  utils::read.csv(oligovigil_url(base_url, "/api/download/benchmark_baseline_results.csv"), stringsAsFactors = FALSE)
}

oligovigil_benchmark_tasks <- function(base_url = "https://oligovigil.pages.dev") {
  utils::read.csv(oligovigil_url(base_url, "/api/download/benchmark_task_cards.csv"), stringsAsFactors = FALSE)
}
