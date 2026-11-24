:show-content:

.. meta::
   :description: A test page with planted errors for the doc-quality-review tests.

===========
Attendances
===========

Go to :menuselection:`Attendances app --> Configuration --> Settings`, and enable
:guilabel:`Automatic Check-Out`. Then open :menuselection:`Attendances app --> Configurations`.

You can click the :icon:`fa-trash-o` :guilabel:`(trash)` icon in the top-right corner.

- :guilabel:`automatic check-out`: Lowercase, so it does not match the UI.
- :guilabel:`Frobnicate Timesheets Daily`: Does not exist in Odoo.
- :guilabel:`Device & Location Tracking`: Escaped as &amp; in the XML.

.. image:: planted/shot.png
   :align: center
   :alt: A screenshot.

See :ref:`attendances/this-anchor-does-not-exist` and :doc:`no_such_page`.

The :guilabel:`Kiosk Settings` section is formatted wrongly for US pages.

- :guilabel:`Validation` :icon:`business`: Select a mode:

  - :guilabel:`Mode A`: First.
  - :guilabel:`Mode B`: Second.

- :guilabel:`Check-Out` :icon:`business`: Second top-level item.
- :guilabel:`Tracking`: Third top-level item.
