# -*- coding: utf-8 -*-
# D.1 — Portal controller for FSD Sign-off

import base64

from markupsafe import Markup

from odoo import fields, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class BAPortalController(CustomerPortal):
    """Portal controller for FSD customer sign-off."""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "fsd_count" in counters:
            partner = request.env.user.partner_id
            values["fsd_count"] = (
                request.env["ba.fsd"]
                .sudo()
                .search_count([
                    ("state", "in", ["pending_signoff", "approved"]),
                    ("project_id.message_partner_ids", "in", [partner.id]),
                ])
            )
        return values

    @http.route("/my/fsd", type="http", auth="user", website=True)
    def portal_fsd_list(self, **kwargs):
        """list FSD documents accessible to the portal user."""
        partner = request.env.user.partner_id
        fsd_records = (
            request.env["ba.fsd"]
            .sudo()
            .search(
                [
                    ("state", "in", ["pending_signoff", "approved"]),
                    (
                        "project_id.message_partner_ids",
                        "in",
                        [partner.id],
                    ),
                ]
            )
        )
        return request.render(
            "adecsol_ba.portal_my_fsd_list",
            {"fsd_records": fsd_records},
        )

    @http.route("/my/fsd/<int:fsd_id>", type="http", auth="user", website=True)
    def portal_fsd_detail(self, fsd_id, **kwargs):
        """FSD detail page with signature widget."""
        fsd = request.env["ba.fsd"].sudo().browse(fsd_id)
        if not fsd.exists():
            return request.redirect("/my/fsd")
        # Authorization: only project followers can view
        partner = request.env.user.partner_id
        if partner not in fsd.project_id.message_partner_ids:
            return request.redirect("/my/fsd")
        return request.render(
            "adecsol_ba.portal_fsd_detail",
            {"fsd": fsd},
        )

    @http.route(
        "/my/fsd/<int:fsd_id>/sign",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_fsd_sign(self, fsd_id, **post):
        """Process the FSD signature from the portal."""
        fsd = request.env["ba.fsd"].sudo().browse(fsd_id)
        if not fsd.exists() or fsd.state != "pending_signoff":
            return request.redirect("/my/fsd")

        signature = post.get("signature")
        signer_title = post.get("signer_title", "").strip()

        # Authorization check
        if request.env.user.partner_id not in fsd.signer_ids:
            return request.redirect("/my/fsd/" + str(fsd_id))

        if not signer_title or not signature:
            # Server-side validation
            return request.redirect("/my/fsd/" + str(fsd_id))

        # Note: signer_name is read from the logged in user as an extra security layer
        signer_name = request.env.user.partner_id.name

        if signature:
            fsd.write(
                {
                    "customer_signature": signature,
                    "customer_signer_name": signer_name,
                    "customer_signer_title": signer_title,
                    "sign_date": fields.Date.context_today(fsd),
                }
            )
            # Post notification to project followers / dev team
            fsd.message_post(
                body=Markup(
                    f"✅ Customer <b>{signer_name}</b> ({signer_title}) "
                    f"has signed off the FSD via Portal."
                ),
                subtype_xmlid="mail.mt_comment",
            )
            
            # Automatically trigger final approve to generate handover tasks
            fsd.sudo().action_final_approve()

            # Send dev notification email
            template = request.env.ref(
                "adecsol_ba.mail_template_fsd_signed_notify_dev",
                raise_if_not_found=False,
            )
            if template:
                template.sudo().send_mail(fsd.id, force_send=True)

        return request.redirect(f"/my/fsd/{fsd_id}")
