"""Nesta levies reform app for rebalancing, testing new levies and social support."""

import streamlit as st

st.set_page_config(
    page_title="Nesta Levies Rebalancing Model", page_icon="🏠", layout="wide"
)

st.title("Nesta Levies Rebalancing Model")
st.markdown("**What is this tool?**")
st.markdown(
    "As part of Nesta's project on [making energy cheaper by rebalancing levies](https://www.nesta.org.uk/project/finding-ways-to-deliver-cheaper-electricity-by-rebalancing-levies/), this tool allows you to model different approaches to rebalancing policy costs between electricity and gas levies, or removing them off bills to general taxation."
)
st.markdown(
    "Results will show the effects of your rebalancing approach on the [**electricity to gas unit cost ratio**](https://www.nesta.org.uk/blog/the-electricity-to-gas-price-ratio-explained-how-a-green-ratio-would-make-bills-cheaper-and-greener/) and the energy bills of different [**UK energy consumer archetypes**](https://www.ofgem.gov.uk/sites/default/files/2024-02/Ofgem_archetypes_update_2024_FinalReport_v4.1.3.pdf)."
)
