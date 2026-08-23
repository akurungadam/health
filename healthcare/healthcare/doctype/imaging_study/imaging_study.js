// Fetches QIDO/WADO with the server's PACS credentials, for studies this user may read.
const DICOM_PROXY = "/api/method/healthcare.healthcare.api.dicom.proxy.fetch";

frappe.ui.form.on("Imaging Study", {
	async refresh(frm) {
		if (!frm.doc.__islocal && frm.doc.preview_json) {
			let series_list = JSON.parse(frm.doc.preview_json || "[]");

			let html = `
				<div class="series-container" style="display:flex; flex-wrap:wrap; gap:16px; margin-bottom:1em;">
			`;

			series_list.forEach((series, index) => {
				html += `
					<div class="series-card" data-series-index="${index}"
						style="
							text-align:center;
							cursor:pointer;
							width:18%;
							border:1px solid #ccc;
							border-radius:7px;
							padding:7px;
							overflow:hidden;
							max-height:220px;
							display:flex;
							flex-direction:column;
							justify-content:space-between;
							box-shadow:0 2px 5px rgba(0,0,0,0.05);">
						<img src="${series.preview_url}" style="width:100%; height:auto; border-radius:5px;" />
						<div style="font-size: 0.85rem; margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${
							series.SeriesDescription || series.SeriesInstanceUID
						}">
							${series.SeriesDescription || series.SeriesInstanceUID}
						</div>
						<div style="color: #888888;">${series.InstanceCount || "0"} ${
							series.Modality
						} images</div>
					</div>
				`;
			});

			html += `
				</div>
				<div id="instance-previews"
					style="margin-top:20px;
					display:none;
					flex-wrap:wrap;
					gap:10px;
					justify-content:left;">
				</div>
			`;

			frm.fields_dict.preview_html.$wrapper.html(html);
			const cards = frm.fields_dict.preview_html.$wrapper.find(".series-card");
			cards.each(function () {
				const card = $(this);
				const index = card.data("series-index");
				const series = series_list[index];

				card.on("click", function () {
					cards.css("border", "1px solid #ccc");
					card.css("border", "3px solid #ccc");

					// Where `yarn build` in viewer/ puts the app: vite's base is
					// /assets/healthcare/viewer/ and its outDir is healthcare/public/viewer,
					// which Frappe serves from there. "/viewer" is not a route and 404s.
					const site = "/assets/healthcare/viewer/";
					const url = new URL(site, window.location.origin);
					url.searchParams.set("studyUID", frm.doc.study_instance_uid);
					url.searchParams.set("seriesUID", series.SeriesInstanceUID);
					url.searchParams.set(
						"objectUID",
						series.Instances?.[0]?.SOPInstanceUID || "",
					);
					// The viewer reaches the PACS through this site, which adds the
					// credentials server-side. Nothing secret goes in the URL: a query
					// string lands in history, access logs and Referer headers.
					url.searchParams.set("proxy", DICOM_PROXY);
					url.searchParams.set("study", frm.doc.name);

					const d = new frappe.ui.Dialog({
						title: `Study: ${frm.doc.study_instance_uid}`,
						size: "large",
						fields: [
							{
								fieldname: "viewer_html",
								fieldtype: "HTML",
								options: `
								<iframe
									src="${url.toString()}"
									width="100%" height="600" frameborder="0"
								></iframe>
							`,
							},
						],
					});
					d.show();
				});
			});
		}
	},
});
