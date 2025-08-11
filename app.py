import streamlit as st
import pandas as pd
import requests
import json
from typing import List, Dict, Any
import io
import time

# Configure page
st.set_page_config(
    page_title="NPI Registry Lookup",
    page_icon="🏥",
    layout="wide"
)

# Title and description
st.title("🏥 NPPES NPI Registry Lookup Tool")
st.markdown("""
This application allows you to look up healthcare provider information using NPI (National Provider Identifier) numbers.
Data is retrieved from the official CMS NPPES NPI Registry API.
""")

# API Configuration
API_BASE_URL = "https://npiregistry.cms.hhs.gov/api/"
API_VERSION = "2.1"

def query_npi_api(npi_number: str) -> Dict[str, Any]:
    """
    Query the NPPES NPI Registry API for a specific NPI number.
    
    Args:
        npi_number: The 10-digit NPI number to query
        
    Returns:
        Dictionary containing the API response
    """
    try:
        params = {
            "version": API_VERSION,
            "number": npi_number
        }
        
        response = requests.get(API_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed for NPI {npi_number}: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse API response for NPI {npi_number}: {str(e)}")
        return None

def extract_provider_info(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant provider information from API response.
    
    Args:
        api_response: The raw API response
        
    Returns:
        Dictionary with extracted provider information
    """
    if not api_response or "results" not in api_response or len(api_response["results"]) == 0:
        return None
    
    result = api_response["results"][0]
    basic = result.get("basic", {})
    addresses = result.get("addresses", [])
    taxonomies = result.get("taxonomies", [])
    other_names = result.get("other_names", [])
    
    # Extract primary practice location (first address)
    primary_location = {}
    if len(addresses) > 0:
        primary = addresses[0]
        primary_location = {
            "address_1": primary.get("address_1", ""),
            "address_2": primary.get("address_2", ""),
            "city": primary.get("city", ""),
            "state": primary.get("state", ""),
            "postal_code": primary.get("postal_code", ""),
            "country": primary.get("country_name", ""),
            "telephone": primary.get("telephone_number", ""),
            "fax": primary.get("fax_number", "")
        }
    
    # Extract mailing address (second address if exists)
    mailing_address = {}
    if len(addresses) > 1:
        mailing = addresses[1]
        mailing_address = {
            "address_1": mailing.get("address_1", ""),
            "address_2": mailing.get("address_2", ""),
            "city": mailing.get("city", ""),
            "state": mailing.get("state", ""),
            "postal_code": mailing.get("postal_code", ""),
            "country": mailing.get("country_name", "")
        }
    
    # Extract DBA names (Doing Business As)
    dba_names = []
    for other_name in other_names:
        if other_name.get("type") == "3":  # Type 3 is typically DBA
            dba_names.append(other_name.get("name", ""))
    
    # Extract primary taxonomy
    primary_taxonomy = ""
    taxonomy_description = ""
    if taxonomies:
        for tax in taxonomies:
            if tax.get("primary", False):
                primary_taxonomy = tax.get("code", "")
                taxonomy_description = tax.get("desc", "")
                break
        # If no primary found, use first taxonomy
        if not primary_taxonomy and taxonomies:
            primary_taxonomy = taxonomies[0].get("code", "")
            taxonomy_description = taxonomies[0].get("desc", "")
    
    provider_info = {
        "npi": result.get("number", ""),
        "entity_type": "Individual" if result.get("enumeration_type") == "NPI-1" else "Organization",
        "facility_name": basic.get("name", "") if result.get("enumeration_type") == "NPI-2" else "",
        "name": basic.get("name", "") if result.get("enumeration_type") == "NPI-2" else f"{basic.get('first_name', '')} {basic.get('last_name', '')}".strip(),
        "doing_business_as": ", ".join(dba_names) if dba_names else "",
        "first_name": basic.get("first_name", ""),
        "last_name": basic.get("last_name", ""),
        "organization_name": basic.get("name", "") if result.get("enumeration_type") == "NPI-2" else "",
        "primary_taxonomy": primary_taxonomy,
        "taxonomy_description": taxonomy_description,
        "primary_practice_address": f"{primary_location.get('address_1', '')} {primary_location.get('address_2', '')}".strip(),
        "primary_practice_city": primary_location.get("city", ""),
        "primary_practice_state": primary_location.get("state", ""),
        "primary_practice_zip": primary_location.get("postal_code", ""),
        "primary_practice_phone": primary_location.get("telephone", ""),
        "primary_practice_fax": primary_location.get("fax", ""),
        "mailing_address": f"{mailing_address.get('address_1', '')} {mailing_address.get('address_2', '')}".strip(),
        "mailing_city": mailing_address.get("city", ""),
        "mailing_state": mailing_address.get("state", ""),
        "mailing_zip": mailing_address.get("postal_code", ""),
        "status": basic.get("status", ""),
        "last_updated": basic.get("last_updated", ""),
        "enumeration_date": basic.get("enumeration_date", ""),
        "authorized_official_first": basic.get("authorized_official_first_name", ""),
        "authorized_official_last": basic.get("authorized_official_last_name", ""),
        "authorized_official_title": basic.get("authorized_official_title_or_position", ""),
        "authorized_official_phone": basic.get("authorized_official_telephone_number", "")
    }
    
    return provider_info

def validate_npi(npi: str) -> bool:
    """
    Validate NPI number format (10 digits).
    
    Args:
        npi: NPI number to validate
        
    Returns:
        True if valid, False otherwise
    """
    npi = npi.strip()
    return len(npi) == 10 and npi.isdigit()

def process_npi_list(npi_list: List[str], facility_focus: bool = True, show_all: bool = False) -> pd.DataFrame:
    """
    Process a list of NPI numbers and return results as a DataFrame.
    
    Args:
        npi_list: List of NPI numbers to process
        facility_focus: Whether to prioritize facility information
        show_all: Whether to show all columns
        
    Returns:
        DataFrame with provider information
    """
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, npi in enumerate(npi_list):
        npi = npi.strip()
        if not npi:
            continue
            
        status_text.text(f"Processing NPI {npi} ({i+1}/{len(npi_list)})")
        
        if not validate_npi(npi):
            results.append({
                "npi": npi,
                "error": "Invalid NPI format (must be 10 digits)"
            })
        else:
            api_response = query_npi_api(npi)
            if api_response:
                provider_info = extract_provider_info(api_response)
                if provider_info:
                    results.append(provider_info)
                else:
                    results.append({
                        "npi": npi,
                        "error": "No results found"
                    })
            else:
                results.append({
                    "npi": npi,
                    "error": "API request failed"
                })
        
        progress_bar.progress((i + 1) / len(npi_list))
        time.sleep(0.1)  # Rate limiting
    
    progress_bar.empty()
    status_text.empty()
    
    df = pd.DataFrame(results)
    
    # Reorder columns based on facility focus
    if not df.empty and 'error' not in df.columns:
        if facility_focus:
            # Prioritize facility columns for organizations
            priority_cols = ['npi', 'entity_type', 'facility_name', 'doing_business_as', 
                           'primary_practice_city', 'primary_practice_state', 
                           'primary_practice_zip', 'primary_practice_phone']
        else:
            priority_cols = ['npi', 'entity_type', 'name', 'primary_practice_city', 
                           'primary_practice_state', 'primary_practice_zip', 
                           'primary_practice_phone']
        
        if not show_all:
            # Show only priority columns
            available_cols = [col for col in priority_cols if col in df.columns]
            other_cols = [col for col in df.columns if col not in available_cols]
            df = df[available_cols + other_cols[:3]]  # Add a few more columns
    
    return df

# Main app interface
st.markdown("---")

# Settings
with st.expander("⚙️ Display Settings"):
    facility_focus = st.checkbox("Facility Focus Mode", value=True, 
                                help="Prioritize facility/organization information in results")
    show_all_columns = st.checkbox("Show All Data Columns", value=False,
                                  help="Display all available data fields in batch results")

# Input methods
st.subheader("📝 Input NPI Numbers")

tab1, tab2, tab3 = st.tabs(["Single NPI", "Multiple NPIs (Text)", "Upload CSV"])

with tab1:
    st.markdown("Enter a single NPI number for lookup")
    single_npi = st.text_input("NPI Number (10 digits):", placeholder="1234567890")
    
    if st.button("Look Up Single NPI", type="primary"):
        if single_npi:
            if validate_npi(single_npi):
                with st.spinner(f"Looking up NPI {single_npi}..."):
                    api_response = query_npi_api(single_npi)
                    if api_response:
                        provider_info = extract_provider_info(api_response)
                        if provider_info:
                            st.success("✅ Provider found!")
                            
                            # Display provider information
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("### Basic Information")
                                st.write(f"**NPI:** {provider_info['npi']}")
                                
                                # Emphasize facility name for organizations
                                if provider_info['entity_type'] == "Organization":
                                    st.write(f"**Facility/Organization:** {provider_info['facility_name']}")
                                    if provider_info['doing_business_as']:
                                        st.write(f"**Doing Business As:** {provider_info['doing_business_as']}")
                                else:
                                    st.write(f"**Name:** {provider_info['name']}")
                                
                                st.write(f"**Entity Type:** {provider_info['entity_type']}")
                                st.write(f"**Status:** {provider_info['status']}")
                                st.write(f"**Enumeration Date:** {provider_info.get('enumeration_date', 'N/A')}")
                                st.write(f"**Last Updated:** {provider_info['last_updated']}")
                                
                                if provider_info['taxonomy_description']:
                                    st.markdown("### Specialty")
                                    st.write(f"**Primary Taxonomy:** {provider_info['taxonomy_description']}")
                                    st.write(f"**Taxonomy Code:** {provider_info['primary_taxonomy']}")
                            
                            with col2:
                                st.markdown("### Practice Location")
                                if provider_info['primary_practice_address']:
                                    st.write(f"**Address:** {provider_info['primary_practice_address']}")
                                    st.write(f"**City:** {provider_info['primary_practice_city']}")
                                    st.write(f"**State:** {provider_info['primary_practice_state']}")
                                    st.write(f"**ZIP:** {provider_info['primary_practice_zip']}")
                                    if provider_info['primary_practice_phone']:
                                        st.write(f"**Phone:** {provider_info['primary_practice_phone']}")
                                    if provider_info['primary_practice_fax']:
                                        st.write(f"**Fax:** {provider_info['primary_practice_fax']}")
                                
                                if provider_info['authorized_official_first']:
                                    st.markdown("### Authorized Official")
                                    st.write(f"**Name:** {provider_info['authorized_official_first']} {provider_info['authorized_official_last']}")
                                    if provider_info['authorized_official_title']:
                                        st.write(f"**Title:** {provider_info['authorized_official_title']}")
                                    if provider_info['authorized_official_phone']:
                                        st.write(f"**Phone:** {provider_info['authorized_official_phone']}")
                        else:
                            st.warning("No provider found with this NPI number.")
                    else:
                        st.error("Failed to query the NPI Registry API.")
            else:
                st.error("Invalid NPI format. Please enter a 10-digit number.")
        else:
            st.warning("Please enter an NPI number.")

with tab2:
    st.markdown("Enter multiple NPI numbers (one per line)")
    multi_npi_text = st.text_area("NPI Numbers:", height=150, placeholder="1234567890\n0987654321\n1122334455")
    
    if st.button("Look Up Multiple NPIs", type="primary"):
        if multi_npi_text:
            npi_list = [npi.strip() for npi in multi_npi_text.split('\n') if npi.strip()]
            if npi_list:
                st.info(f"Processing {len(npi_list)} NPI numbers...")
                results_df = process_npi_list(npi_list, facility_focus, show_all_columns)
                
                if not results_df.empty:
                    st.success(f"✅ Processed {len(results_df)} NPI numbers")
                    
                    # Summary statistics for organizations
                    if 'entity_type' in results_df.columns:
                        org_count = len(results_df[results_df['entity_type'] == 'Organization'])
                        ind_count = len(results_df[results_df['entity_type'] == 'Individual'])
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total NPIs", len(results_df))
                        with col2:
                            st.metric("Organizations/Facilities", org_count)
                        with col3:
                            st.metric("Individual Providers", ind_count)
                    
                    # Display results
                    st.dataframe(results_df, use_container_width=True)
                    
                    # Download button
                    csv = results_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv,
                        file_name="npi_lookup_results.csv",
                        mime="text/csv"
                    )
            else:
                st.warning("Please enter at least one NPI number.")
        else:
            st.warning("Please enter NPI numbers.")

with tab3:
    st.markdown("Upload a CSV file with NPI numbers")
    st.info("The CSV file should have a column named 'NPI' or the first column will be used.")
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            
            # Find NPI column
            npi_column = None
            for col in df.columns:
                if 'NPI' in col.upper():
                    npi_column = col
                    break
            
            if npi_column is None:
                npi_column = df.columns[0]
                st.info(f"No 'NPI' column found. Using first column: '{npi_column}'")
            
            npi_list = df[npi_column].astype(str).tolist()
            
            st.write(f"Found {len(npi_list)} NPI numbers in column '{npi_column}'")
            
            if st.button("Process Uploaded NPIs", type="primary"):
                results_df = process_npi_list(npi_list, facility_focus, show_all_columns)
                
                if not results_df.empty:
                    st.success(f"✅ Processed {len(results_df)} NPI numbers")
                    
                    # Summary statistics for organizations
                    if 'entity_type' in results_df.columns:
                        org_count = len(results_df[results_df['entity_type'] == 'Organization'])
                        ind_count = len(results_df[results_df['entity_type'] == 'Individual'])
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total NPIs", len(results_df))
                        with col2:
                            st.metric("Organizations/Facilities", org_count)
                        with col3:
                            st.metric("Individual Providers", ind_count)
                    
                    # Display results
                    st.dataframe(results_df, use_container_width=True)
                    
                    # Download button
                    csv = results_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv,
                        file_name="npi_lookup_results.csv",
                        mime="text/csv"
                    )
                    
        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 12px;'>
    Data source: NPPES NPI Registry API v2.1 | 
    Note: Issuance of an NPI does not ensure or validate that the Health Care Provider is Licensed or Credentialed
</div>
""", unsafe_allow_html=True)
