library(ggplot2)
library(patchwork)
library(grid)

final_dir <- "C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07"
fig_dir <- file.path(final_dir, "figures")
source_dir <- file.path(fig_dir, "source_data")
dir.create(source_dir, showWarnings = FALSE, recursive = TRUE)

out_base <- file.path(fig_dir, "FIG5_peer_comparison")

db_order <- c("OligoVigil", "theRNA", "siRNAEfficacyDB", "CMsiRNAdb", "siRNAmod", "CRISPRoffT")

set_df <- data.frame(
  resource = factor(c("OligoVigil", "CRISPRoffT", "siRNAEfficacyDB"),
                    levels = c("siRNAEfficacyDB", "CRISPRoffT", "OligoVigil")),
  unique_pmids = c(660, 74, 7),
  class = c("this resource", "CRISPR/Cas off-target", "siRNA efficacy"),
  stringsAsFactors = FALSE
)

intersection_df <- data.frame(
  comparison = c("OligoVigil vs CRISPRoffT", "OligoVigil vs siRNAEfficacyDB",
                 "CRISPRoffT vs siRNAEfficacyDB", "All three"),
  overlap_pmids = c(0, 0, 0, 0),
  stringsAsFactors = FALSE
)

feature_names <- c(
  "Total curated records",
  "Exact source location",
  "Curator audit trail",
  "Inter-curator check",
  "Machine-stage FAR audit",
  "Benchmark splits",
  "Deterministic baselines",
  "Structured assay metadata",
  "Per-position chemistry",
  "Off-target gene resolution",
  "No-login portal",
  "API / OpenAPI",
  "Agent-readable metadata",
  "Bulk download",
  "Versioned release",
  "Named maintainer"
)

feature_group <- c(
  "scale", "provenance", "provenance", "provenance", "provenance",
  "reuse", "reuse", "metadata", "metadata", "metadata",
  "access", "access", "access", "access", "access", "access"
)

values <- matrix(
  c(
    "yes", "yes", "yes", "yes", "yes", "yes",
    "yes", "yes", "partial", "partial", "partial", "partial",
    "yes", "partial", "no", "no", "no", "partial",
    "yes", "no", "no", "no", "no", "no",
    "yes", "no", "no", "no", "no", "no",
    "yes", "no", "partial", "no", "no", "partial",
    "yes", "no", "no", "no", "no", "no",
    "partial", "partial", "yes", "partial", "no", "partial",
    "no", "partial", "no", "yes", "yes", "no",
    "partial", "no", "no", "no", "no", "yes",
    "yes", "yes", "yes", "yes", "no", "yes",
    "yes", "partial", "partial", "partial", "no", "partial",
    "yes", "no", "no", "no", "no", "partial",
    "yes", "partial", "partial", "partial", "partial", "partial",
    "yes", "partial", "partial", "partial", "partial", "partial",
    "yes", "yes", "yes", "yes", "partial", "yes"
  ),
  nrow = length(feature_names),
  byrow = TRUE,
  dimnames = list(feature_names, db_order)
)

feature_df <- as.data.frame(as.table(values), stringsAsFactors = FALSE)
names(feature_df) <- c("feature", "resource", "support")
feature_df$feature <- factor(feature_df$feature, levels = rev(feature_names))
feature_df$resource <- factor(feature_df$resource, levels = db_order)
feature_df$group <- feature_group[match(as.character(feature_df$feature), feature_names)]
feature_df$score <- c(yes = 1, partial = 0.5, no = 0)[feature_df$support]

write.csv(set_df, file.path(source_dir, "FIG5_closest_work_audit_v2_sets.csv"), row.names = FALSE)
write.csv(intersection_df, file.path(source_dir, "FIG5_closest_work_audit_v2_intersections.csv"), row.names = FALSE)
write.csv(feature_df, file.path(source_dir, "FIG5_closest_work_audit_v2_features.csv"), row.names = FALSE)

palette <- c(
  yes = "#0E776E",
  partial = "#E0A23A",
  no = "#D7DDE6"
)

resource_colors <- c(
  "OligoVigil" = "#0E776E",
  "CRISPRoffT" = "#C87539",
  "siRNAEfficacyDB" = "#5F78A7"
)

base_theme <- theme_minimal(base_family = "Arial", base_size = 8) +
  theme(
    panel.grid.minor = element_blank(),
    plot.title = element_text(face = "bold", size = 10, colour = "#092247"),
    plot.subtitle = element_text(size = 7.2, colour = "#51627C"),
    axis.title = element_text(size = 7.2, colour = "#25344F"),
    axis.text = element_text(size = 7, colour = "#14213D"),
    legend.title = element_text(size = 7, colour = "#25344F"),
    legend.text = element_text(size = 6.8, colour = "#25344F"),
    strip.text = element_text(face = "bold", size = 7, colour = "#092247"),
    plot.margin = margin(5, 8, 5, 8)
  )

p_a <- ggplot(set_df, aes(x = unique_pmids, y = resource, colour = resource)) +
  geom_segment(aes(x = 0, xend = unique_pmids, yend = resource), linewidth = 1.5, alpha = 0.55) +
  geom_point(size = 5.5, fill = "white", shape = 21, stroke = 1.2) +
  geom_text(aes(label = unique_pmids), nudge_x = 72, hjust = 0, size = 3.0,
            colour = "#092247", fontface = "bold") +
  annotate("label", x = 430, y = 1.55, label = "All pairwise intersections = 0",
           label.r = unit(2, "pt"), fill = "#FFF6E8",
           colour = "#9A4D0B", size = 2.35, fontface = "bold") +
  scale_colour_manual(values = resource_colors, guide = "none") +
  scale_x_continuous(limits = c(0, 850), breaks = c(0, 250, 500, 750),
                     expand = expansion(mult = c(0, 0.03))) +
  labs(
    title = "A  Source-PMID disjointness",
    x = "unique source PMIDs", y = NULL
  ) +
  base_theme +
  theme(panel.grid.major.y = element_blank())

p_b <- ggplot(feature_df, aes(x = resource, y = feature)) +
  annotate("rect", xmin = 0.5, xmax = 1.5, ymin = -Inf, ymax = Inf,
           fill = "#E9F5F3", alpha = 0.8) +
  geom_point(aes(fill = support, size = score), shape = 21,
             colour = "#23324A", stroke = 0.35) +
  geom_text(
    data = subset(feature_df, support %in% c("yes", "partial") & resource == "OligoVigil"),
    aes(label = ifelse(support == "yes", "✓", "·")),
    colour = "white", size = 2.2, fontface = "bold"
  ) +
  scale_fill_manual(values = palette, breaks = c("yes", "partial", "no"),
                    labels = c("yes", "partial", "absent/unknown")) +
  scale_size_continuous(range = c(2.2, 4.2), guide = "none") +
  labs(
    title = "B  Closest-work feature fingerprint",
    x = NULL, y = NULL, fill = "support"
  ) +
  base_theme +
  theme(
    axis.text.x = element_text(angle = 35, hjust = 1, vjust = 1, face = "bold"),
    panel.grid.major.x = element_line(colour = "#E3E8EF", linewidth = 0.25),
    panel.grid.major.y = element_line(colour = "#EDF1F5", linewidth = 0.22),
    legend.position = "bottom",
    legend.box.margin = margin(-4, 0, 0, 0)
  )

fig <- p_a + p_b + plot_layout(widths = c(0.82, 1.95)) +
  plot_annotation(
    title = "Closest-work audit",
    subtitle = "OligoVigil is not another efficacy catalogue: its differentiator is source-level provenance and reusable audit metadata.",
    theme = theme(
      plot.title = element_text(family = "Arial", face = "bold", size = 13, colour = "#092247"),
      plot.subtitle = element_text(family = "Arial", size = 8, colour = "#51627C"),
      plot.margin = margin(8, 8, 8, 8)
    )
  )

ggsave(paste0(out_base, ".pdf"), fig, width = 183, height = 115, units = "mm", device = cairo_pdf)
ggsave(paste0(out_base, ".svg"), fig, width = 183, height = 115, units = "mm", device = svglite::svglite)
ggsave(paste0(out_base, ".png"), fig, width = 183, height = 115, units = "mm", dpi = 600)
ragg::agg_tiff(paste0(out_base, ".tiff"), width = 183 / 25.4, height = 115 / 25.4,
               units = "in", res = 600, compression = "lzw")
print(fig)
dev.off()
