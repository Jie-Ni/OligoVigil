library(ggplot2)
library(patchwork)
library(readr)
library(dplyr)
library(scales)
library(ggalluvial)
library(ggforce)
library(ggrepel)

args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
script_path <- if (length(file_arg)) sub("^--file=", "", file_arg[[1]]) else "scripts/make_fig3_evidence_landscape_v3.R"
root <- normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
data_path <- file.path(root, "figures", "source_data", "FIG3_evidence_landscape_v3_rows.csv")
out_base <- file.path(root, "figures", "FIG3_evidence_landscape_v3")

rows <- read_csv(data_path, show_col_types = FALSE)

short_endpoint <- function(x) {
  recode(
    x,
    "hepatic" = "liver",
    "renal" = "renal",
    "immune" = "immune",
    "hematologic" = "blood",
    "neurological" = "neuro",
    "genotoxicity" = "genotox",
    "chemistry/delivery" = "chem/delivery",
    "general/other safety" = "general",
    "seed-mediated" = "seed",
    "mismatch/hybridization" = "mismatch",
    "transcriptome-wide" = "transcriptome",
    "general specificity" = "specificity",
    .default = x
  )
}

pal <- c(
  "toxicity" = "#2c7a7b",
  "off-target" = "#c06c3f",
  "ASO/gapmer" = "#205072",
  "siRNA" = "#3a8f7b",
  "mixed ASO/siRNA" = "#d08c2c",
  "PMO" = "#6c5b7b",
  "CpG ODN" = "#b84a3a",
  "other" = "#737373",
  "A" = "#1f766e",
  "B" = "#6aa6a0",
  "C" = "#d08c2c",
  "benchmark split" = "#3266a8",
  "release only" = "#8a8f98"
)

theme_set(
  theme_classic(base_size = 6.4, base_family = "Arial") +
    theme(
      plot.title = element_text(size = 7.4, face = "bold", colour = "#0b2545"),
      plot.subtitle = element_text(size = 5.8, colour = "#475569"),
      plot.tag = element_text(size = 7, face = "bold", colour = "#0b2545"),
      axis.line = element_line(linewidth = 0.32, colour = "#1f2937"),
      axis.ticks = element_line(linewidth = 0.28, colour = "#1f2937"),
      legend.position = "bottom",
      legend.title = element_blank(),
      legend.text = element_text(size = 5.4),
      panel.grid = element_blank(),
      plot.margin = margin(4, 6, 4, 4)
    )
)

flow_data <- rows %>%
  mutate(
    modality_stage = recode(
      modality_group,
      "ASO/gapmer" = "ASO",
      "mixed ASO/siRNA" = "ASO/siRNA",
      .default = modality_group
    ),
    endpoint_stage = paste0(if_else(domain == "toxicity", "tox: ", "off: "), short_endpoint(endpoint_group)),
    grade_stage = paste0("G", grade),
    reuse_stage = recode(benchmark_status, "benchmark split" = "benchmark", "release only" = "release-only")
  ) %>%
  count(modality_stage, domain, endpoint_stage, grade_stage, reuse_stage, name = "n") %>%
  filter(n >= 2)

modality_labels <- tibble::tibble(
  label = c("ASO", "ASO/siRNA", "siRNA"),
  x = c(0.86, 0.86, 0.86),
  y = c(585, 385, 150)
)

p1 <- ggplot(
  flow_data,
  aes(
    axis1 = modality_stage,
    axis2 = domain,
    axis3 = endpoint_stage,
    axis4 = grade_stage,
    axis5 = reuse_stage,
    y = n
  )
) +
  geom_alluvium(aes(fill = domain), alpha = 0.48, width = 0.14, knot.pos = 0.35) +
  geom_stratum(width = 0.16, fill = "#f8fafc", colour = "#334155", linewidth = 0.2) +
  geom_text(
    stat = "stratum",
    aes(label = after_stat(ifelse(
      count >= 75 &
        !grepl("^(tox|off):", stratum) &
        !(stratum %in% c("ASO", "ASO/siRNA", "siRNA", "off-target", "toxicity", "benchmark", "release-only")),
      as.character(stratum),
      ""
    ))),
    size = 1.35,
    colour = "#0f172a"
  ) +
  geom_text(
    data = modality_labels,
    aes(x = x, y = y, label = label),
    inherit.aes = FALSE,
    hjust = 1,
    size = 1.28,
    colour = "#0f172a",
    lineheight = 0.88
  ) +
  scale_x_discrete(limits = c("modality", "domain", "endpoint family", "grade", "reuse"), expand = c(0.15, 0.08)) +
  scale_fill_manual(values = pal[c("toxicity", "off-target")]) +
  labs(
    title = "Evidence flow from molecule class to reusable records",
    subtitle = "Each ribbon is a curator-verified release stratum; width is row count",
    x = NULL,
    y = "release rows"
  ) +
  theme(axis.text.y = element_blank(), axis.ticks.y = element_blank(), legend.position = "none")

edge_data <- rows %>%
  count(modality_group, endpoint_group, domain, name = "n") %>%
  filter(n >= 5)

modalities <- edge_data %>%
  group_by(modality_group) %>%
  summarise(total = sum(n), .groups = "drop") %>%
  arrange(desc(total)) %>%
  mutate(x = 0.08, y = seq(0.88, 0.18, length.out = n()))

endpoints <- edge_data %>%
  group_by(endpoint_group, domain) %>%
  summarise(total = sum(n), .groups = "drop") %>%
  arrange(domain, desc(total)) %>%
  mutate(x = 0.92, y = seq(0.90, 0.12, length.out = n()))

edges <- edge_data %>%
  left_join(select(modalities, modality_group, x0 = x, y0 = y), by = "modality_group") %>%
  left_join(select(endpoints, endpoint_group, x1 = x, y1 = y), by = "endpoint_group")

nodes <- bind_rows(
  transmute(modalities, node = modality_group, total, x, y, type = "modality"),
  transmute(endpoints, node = endpoint_group, total, x, y, type = domain)
) 
nodes <- nodes %>%
  mutate(
    node = short_endpoint(node),
    label_x = if_else(type == "modality", x - 0.035, x + 0.035),
    hjust_value = if_else(type == "modality", 1, 0)
  )

p2 <- ggplot() +
  geom_curve(
    data = edges,
    aes(x = x0, y = y0, xend = x1, yend = y1, linewidth = n, colour = domain),
    curvature = 0.28,
    alpha = 0.34,
    lineend = "round"
  ) +
  geom_point(data = nodes, aes(x, y, size = total, fill = type), shape = 21, colour = "white", stroke = 0.38) +
  geom_text(
    data = nodes,
    aes(x = label_x, y = y, label = node, hjust = hjust_value),
    size = 1.75,
    colour = "#0f172a",
    lineheight = 0.86
  ) +
  scale_colour_manual(values = pal[c("toxicity", "off-target")]) +
  scale_fill_manual(values = c("modality" = "#dbeafe", "toxicity" = "#cde7e3", "off-target" = "#f6d2bd")) +
  scale_size(range = c(1.9, 6.6)) +
  scale_linewidth(range = c(0.2, 2.4)) +
  coord_cartesian(xlim = c(-0.08, 1.08), ylim = c(0.04, 0.96), expand = FALSE, clip = "off") +
  labs(
    title = "Mechanism and endpoint connectivity",
    subtitle = "Edges connect molecule classes to safety or off-target evidence families"
  ) +
  theme_void(base_family = "Arial") +
  theme(
    legend.position = "none",
    plot.title = element_text(size = 7.4, face = "bold", colour = "#0b2545"),
    plot.subtitle = element_text(size = 5.8, colour = "#475569"),
    plot.margin = margin(4, 6, 4, 4)
  )

year_data <- rows %>%
  filter(!is.na(publication_year), publication_year > 1990) %>%
  distinct(source_id, domain, publication_year, source_depth) %>%
  count(publication_year, domain, source_depth, name = "sources") %>%
  group_by(publication_year, domain) %>%
  mutate(total_year_domain = sum(sources)) %>%
  ungroup()

p3 <- ggplot(year_data, aes(publication_year, domain)) +
  geom_point(
    aes(size = total_year_domain, fill = source_depth),
    shape = 21,
    colour = "#0f172a",
    stroke = 0.18,
    alpha = 0.78,
    position = position_jitter(height = 0.08, width = 0)
  ) +
  geom_smooth(aes(group = domain, colour = domain), method = "loess", formula = y ~ x, se = FALSE, linewidth = 0.55, alpha = 0.7) +
  scale_fill_manual(values = c("PMC full text" = "#2c7a7b", "abstract/metadata" = "#d08c2c")) +
  scale_colour_manual(values = pal[c("toxicity", "off-target")]) +
  scale_size(range = c(1.8, 8.5), breaks = c(1, 5, 10, 20, 40)) +
  scale_x_continuous(breaks = pretty_breaks(6)) +
  labs(
    title = "Source-year landscape",
    subtitle = "Bubble area is distinct source count; fill shows grounding depth",
    x = "publication year",
    y = NULL
  ) +
  theme(legend.position = "none")

state_data <- bind_rows(
  rows %>% count(track = "Domain", segment = domain, name = "n"),
  rows %>% count(track = "Grade", segment = grade, name = "n"),
  rows %>% count(track = "Reuse", segment = benchmark_status, name = "n"),
  rows %>% count(track = "Grounding", segment = source_depth, name = "n")
) %>%
  mutate(
    track = factor(track, levels = c("Grounding", "Reuse", "Grade", "Domain")),
    segment = recode(segment, "benchmark split" = "benchmark", "release only" = "release-only"),
    label = paste0(segment, "\n", n)
  ) %>%
  group_by(track) %>%
  mutate(frac = n / sum(n), label = if_else(frac >= 0.11, label, "")) %>%
  ungroup()

state_palette <- c(
  pal[c("toxicity", "off-target", "A", "B", "C")],
  "benchmark" = "#3266a8",
  "release-only" = "#8a8f98",
  "PMC full text" = "#4f9a8b",
  "abstract/metadata" = "#f4a261"
)

p4 <- ggplot(state_data, aes(x = n, y = track, fill = segment)) +
  geom_col(position = "fill", width = 0.62, colour = "white", linewidth = 0.28) +
  geom_text(
    aes(label = label),
    position = position_fill(vjust = 0.5),
    size = 1.58,
    lineheight = 0.82,
    colour = "#0f172a"
  ) +
  scale_fill_manual(values = state_palette, na.value = "#b8b8b8") +
  scale_x_continuous(labels = percent_format(accuracy = 1), expand = c(0, 0)) +
  labs(
    title = "Reusable evidence state",
    subtitle = "Four orthogonal release states; labels show counts",
    x = "share of release rows",
    y = NULL
  ) +
  theme(
    legend.position = "none",
    plot.title = element_text(size = 7.4, face = "bold", colour = "#0b2545"),
    plot.subtitle = element_text(size = 5.8, colour = "#475569"),
    axis.text.y = element_text(size = 5.8, colour = "#0f172a"),
    axis.text.x = element_text(size = 5.2, colour = "#475569"),
    axis.ticks.y = element_blank(),
    axis.line.y = element_blank(),
    plot.margin = margin(4, 6, 4, 4)
  )

fig <- ((p1 / p2) | (p3 / p4)) +
  plot_layout(widths = c(1.28, 1), heights = c(1, 1)) +
  plot_annotation(
    title = "OligoVigil evidence landscape",
    subtitle = "A source-anchored map of molecule classes, safety/off-target mechanisms, literature grounding and benchmark reuse",
    tag_levels = "A",
    theme = theme(
      plot.title = element_text(size = 9, face = "bold", colour = "#0b2545"),
      plot.subtitle = element_text(size = 6.2, colour = "#475569"),
      plot.tag = element_text(size = 7.2, face = "bold", colour = "#0b2545")
    )
  )

ggsave(paste0(out_base, ".pdf"), fig, width = 183, height = 160, units = "mm", device = cairo_pdf)
ggsave(paste0(out_base, ".svg"), fig, width = 183, height = 160, units = "mm")
ggsave(paste0(out_base, ".png"), fig, width = 183, height = 160, units = "mm", dpi = 600)
ggsave(paste0(out_base, ".tiff"), fig, width = 183, height = 160, units = "mm", dpi = 600)
