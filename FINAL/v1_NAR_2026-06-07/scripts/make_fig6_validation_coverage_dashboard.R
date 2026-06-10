library(ggplot2)
library(patchwork)
library(readr)
library(dplyr)
library(scales)

args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
script_path <- if (length(file_arg)) sub("^--file=", "", file_arg[[1]]) else "scripts/make_fig6_validation_coverage_dashboard.R"
root <- normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
data_path <- file.path(root, "figures", "source_data", "FIG6_validation_coverage_dashboard_v12.csv")
out_base <- file.path(root, "figures", "FIG6_validation_coverage_dashboard_v12")

source_data <- read_csv(data_path, show_col_types = FALSE)

theme_set(
  theme_classic(base_size = 6.6, base_family = "Arial") +
    theme(
      axis.line = element_line(linewidth = 0.35, colour = "#1f2937"),
      axis.ticks = element_line(linewidth = 0.35, colour = "#1f2937"),
      legend.position = "none",
      plot.title = element_text(size = 7.6, face = "bold", colour = "#0b2545"),
      plot.subtitle = element_text(size = 6.2, colour = "#475569"),
      plot.tag = element_text(size = 9, face = "bold", colour = "#0b2545"),
      panel.grid = element_blank(),
      plot.margin = margin(4, 8, 4, 4)
    )
)

field_data <- source_data %>%
  filter(panel == "field_completeness") %>%
  mutate(
    group = factor(group, levels = c("toxicity", "off-target")),
    category = factor(
      category,
      levels = c(
        "off-target gene/mechanism",
        "dose",
        "sequence/modification",
        "evidence grade",
        "PMID/DOI/source location"
      )
    )
  )

p1 <- ggplot(field_data, aes(group, category, fill = value)) +
  geom_tile(width = 0.9, height = 0.82, colour = "white", linewidth = 0.4) +
  geom_text(aes(label = paste0(round(value, 1), "%")), size = 2.05, colour = "#0f172a") +
  scale_fill_gradientn(colours = c("#f4a261", "#f7e7b5", "#75b7a8", "#1f766e"), limits = c(0, 100)) +
  labs(title = "Core-field completeness", subtitle = "Complete provenance; sparse sequence/dose fields", x = NULL, y = NULL) +
  theme(axis.text.x = element_text(face = "bold"), axis.ticks = element_blank())

far_data <- source_data %>%
  filter(panel == "far_audit") %>%
  mutate(category = reorder(category, value))

p2 <- ggplot(far_data, aes(value, category)) +
  geom_col(width = 0.68, fill = "#b84a3a") +
  geom_text(aes(label = value), hjust = -0.15, size = 2.2, colour = "#0f172a") +
  scale_x_continuous(expand = expansion(mult = c(0, 0.15))) +
  labs(title = "Machine-stage failure modes", subtitle = "66 false accepts among 90 v1 accept calls", x = "Rows", y = NULL)

kappa_data <- source_data %>%
  filter(panel == "kappa2") %>%
  mutate(
    group = recode(group, curator1_accept = "curator 1: accept", curator1_reject = "curator 1: reject"),
    group = factor(group, levels = c("curator 1: accept", "curator 1: reject")),
    category = recode(category, curator2_accept = "curator 2: accept", curator2_reject = "curator 2: reject", curator2_abstain = "curator 2: abstain"),
    category = factor(category, levels = c("curator 2: accept", "curator 2: reject", "curator 2: abstain"))
  )

p3 <- ggplot(kappa_data, aes(category, group, fill = value)) +
  geom_tile(width = 0.88, height = 0.78, colour = "white", linewidth = 0.4) +
  geom_text(aes(label = value), size = 2.4, colour = "#0f172a") +
  scale_fill_gradient(low = "#f7e7b5", high = "#1f766e") +
  labs(title = "Independent curation check", subtitle = "KAPPA-2: kappa = 0.42; sensitivity kappa = 0.34", x = NULL, y = NULL) +
  theme(axis.text.x = element_text(angle = 18, hjust = 1), axis.ticks = element_blank())

bench_data <- source_data %>%
  filter(panel == "benchmark") %>%
  mutate(
    category = recode(
      category,
      "total verified release" = "verified release",
      "missing toxicity dose" = "missing toxicity dose",
      "Grade A/B reference split" = "Grade A/B split",
      "Grade A/B not yet benchmarked" = "A/B not yet benchmarked",
      "placeholder benchmark rows" = "placeholder split rows"
    ),
    category = reorder(category, value),
    fill_colour = recode(
      group,
      "release rows" = "#2c7a7b",
      "benchmark rows" = "#336699",
      "benchmark gap" = "#d08c2c",
      "metadata gap" = "#9a3f34"
    )
  )

p4 <- ggplot(bench_data, aes(value, category, fill = fill_colour)) +
  geom_col(width = 0.66) +
  geom_text(aes(label = value), hjust = -0.12, size = 2.1, colour = "#0f172a") +
  scale_x_continuous(expand = expansion(mult = c(0, 0.16))) +
  scale_fill_identity() +
  labs(title = "Benchmark and metadata readiness", subtitle = "Reference splits plus residual worklist", x = "Rows", y = NULL)

fig <- (p1 | p2) / (p3 | p4) +
  plot_annotation(
    title = "Release validation and residual curation gaps",
    subtitle = "Completeness, machine-stage false accepts, independent curation, and benchmark readiness",
    tag_levels = "A"
  )

ggsave(paste0(out_base, ".pdf"), fig, width = 183, height = 135, units = "mm", device = cairo_pdf)
ggsave(paste0(out_base, ".svg"), fig, width = 183, height = 135, units = "mm")
ggsave(paste0(out_base, ".png"), fig, width = 183, height = 135, units = "mm", dpi = 600)
ggsave(paste0(out_base, ".tiff"), fig, width = 183, height = 135, units = "mm", dpi = 600)
