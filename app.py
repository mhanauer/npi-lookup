import streamlit as st
import pandas as pd
import requests
import json
from typing import List, Dict, Any
import time

# Configure page
st.set_page_config(
    
    # Extract organization/facility name - the API uses 'organization_name' in basic
    organization_name = ""
    if result.get("enumeration_type") == "NPI-2":
        # For organizations, look in basic.organization_name
        organization_name = basic.get("organization_name", "") or basic.get("name", "") or ""
    
    # Extract provider name for individuals
    provider_name = ""
    if result.get("enumeration_type") == "NPI-1":
        first_name = basic.get("first_name", "")
        last_name = basic.get("last_name", "")
        provider_name = f"{first_name} {last_name}".strip()
    else:
        provider_name = organization_namepage_title="NPI Registry Lookup",
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

def extract_provider_info(api_response: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
    """
    Extract relevant provider information from API response.
    
    Args:
        api_response: The raw API response
        debug: Whether to print debug information
        
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
    # API can return either practiceLocations or practice_locations
    practice_locations = result.get("practiceLocations", []) or result.get("practice_locations", [])
    
    # Debug output
    if debug:
        st.write("DEBUG - Basic info keys:", list(basic.keys()) if basic else "No basic info")
        if basic:
            st.write("DEBUG - Organization name field value:", basic.get("organization_name", "Not found"))
            st.write("DEBUG - Name field value:", basic.get("name", "Not found"))
            st.write("DEBUG - Enumeration type:", result.get("enumeration_type", "Not found"))
    
    # Extract organization/facility name - try multiple possible field names
    organization_name = ""
    if result.get("enumeration_type") == "NPI-2":
        # Try different possible field names for organization
        organization_name = (
            basic.get("organization_name") or 
            basic.get("name") or 
            basic.get("legal_business_name") or 
            basic.get("org_name") or 
            ""
        )
    
    # Extract provider name for individuals
    provider_name = ""
    if result.get("enumeration_type") == "NPI-1":
        first_name = basic.get("first_name", "")
        last_name = basic.get("last_name", "")
        provider_name = f"{first_name} {last_name}".strip()
    else:
        provider_name = organization_name
    
    # Extract addresses - note that the order can vary based on address_purpose
    primary_location = {}
    mailing_address = {}
    
    for address in addresses:
        if address.get("address_purpose") == "LOCATION":
            # This is the primary practice location
            primary_location = {
                "address_1": address.get("address_1", ""),
                "address_2": address.get("address_2", ""),
                "city": address.get("city", ""),
                "state": address.get("state", ""),
                "postal_code": address.get("postal_code", ""),
                "country": address.get("country_name", ""),
                "telephone": address.get("telephone_number", ""),
                "fax": address.get("fax_number", "")
            }
        elif address.get("address_purpose") == "MAILING":
            # This is the mailing address
            mailing_address = {
                "address_1": address.get("address_1", ""),
                "address_2": address.get("address_2", ""),
                "city": address.get("city", ""),
                "state": address.get("state", ""),
                "postal_code": address.get("postal_code", ""),
                "country": address.get("country_name", "")
            }
    
    # Extract DBA names (Doing Business As)
    dba_names = []
    for other_name in other_names:
        # Check if it's a DBA type (code "3" or type "Doing Business As")
        if other_name.get("code") == "3" or other_name.get("type") == "Doing Business As":
            # The field is 'organization_name' for organizations
            name = other_name.get("organization_name", "") or other_name.get("name", "")
            if name and name not in dba_names:
                dba_names.append(name)
    
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
        "facility_name": organization_name,
        "name": provider_name,
        "doing_business_as": ", ".join(dba_names) if dba_names else "",
        "first_name": basic.get("first_name", ""),
        "last_name": basic.get("last_name", ""),
        "organization_name": organization_name,
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
        "authorized_official_phone": basic.get("authorized_official_telephone_number", ""),
        "total_locations": len(practice_locations) + 1 if practice_locations else 1
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
                provider_info = extract_provider_info(api_response, debug=False)
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
with st.expander("⚙️ Display Settings", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        facility_focus = st.checkbox("Facility Focus Mode", value=True, 
                                    help="Prioritize facility/organization information in results")
        show_all_columns = st.checkbox("Show All Data Columns", value=False,
                                      help="Display all available data fields in batch results")
    with col2:
        debug_mode = st.checkbox("Debug Mode", value=False,
                               help="Show API response details for troubleshooting blank fields")

# Input methods
st.subheader("📝 Input NPI Numbers")

tab1, tab2, tab3, tab4 = st.tabs(["Single NPI", "Multiple NPIs (Text)", "Upload CSV", "Advanced Search"])

with tab1:
    st.markdown("Enter a single NPI number for lookup")
    
    # Example NPI for testing
    st.info("💡 Example NPI: **1275271462** (Shriners Hospitals for Children)")
    
    single_npi = st.text_input("NPI Number (10 digits):", placeholder="1234567890")
    
    if st.button("Look Up Single NPI", type="primary"):
        if single_npi:
            if validate_npi(single_npi):
                with st.spinner(f"Looking up NPI {single_npi}..."):
                    api_response = query_npi_api(single_npi)
                    if api_response:
                        # Show raw API response in debug mode
                        if debug_mode:
                            with st.expander("🔍 Raw API Response"):
                                st.json(api_response)
                        
                        provider_info = extract_provider_info(api_response, debug_mode)
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
                                    if provider_info.get('total_locations', 1) > 1:
                                        st.write(f"**Total Locations:** {provider_info.get('total_locations', 1)}")
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
                            
                            # Show all practice locations if there are multiple
                            if provider_info.get('total_locations', 1) > 1:
                                with st.expander(f"📍 View All {provider_info.get('total_locations', 1)} Practice Locations"):
                                    # Check for practice locations in the API response
                                    locations = (api_response['results'][0].get('practiceLocations', []) or 
                                               api_response['results'][0].get('practice_locations', []))
                                    if locations:
                                        # Show primary location first
                                        st.write("**Primary Location:**")
                                        st.write(f"{provider_info['primary_practice_address']}")
                                        st.write(f"{provider_info['primary_practice_city']}, {provider_info['primary_practice_state']} {provider_info['primary_practice_zip']}")
                                        if provider_info['primary_practice_phone']:
                                            st.write(f"Phone: {provider_info['primary_practice_phone']}")
                                        st.write("---")
                                        
                                        # Show additional locations
                                        st.write("**Additional Locations:**")
                                        for i, loc in enumerate(locations, 1):
                                            st.write(f"**Location {i+1}:**")
                                            st.write(f"{loc.get('address_1', '')} {loc.get('address_2', '')}".strip())
                                            st.write(f"{loc.get('city', '')}, {loc.get('state', '')} {loc.get('postal_code', '')}")
                                            if loc.get('telephone_number'):
                                                st.write(f"Phone: {loc.get('telephone_number')}")
                                            st.write("---")
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

with tab4:
    st.markdown("Search for providers using advanced criteria")
    
    col1, col2 = st.columns(2)
    
    with col1:
        search_type = st.selectbox("Provider Type", 
                                  ["All", "Organizations Only", "Individuals Only"])
        org_name = st.text_input("Organization Name (supports wildcards *)", 
                                placeholder="SHRINERS*")
        first_name = st.text_input("First Name (Individual providers)", 
                                  placeholder="John")
        last_name = st.text_input("Last Name (Individual providers)", 
                                 placeholder="Smith")
    
    with col2:
        city = st.text_input("City", placeholder="Philadelphia")
        state = st.text_input("State (2-letter code)", placeholder="PA", max_chars=2)
        postal_code = st.text_input("Postal Code", placeholder="19140")
        taxonomy_desc = st.text_input("Specialty/Taxonomy", 
                                     placeholder="Orthopaedic Surgery")
    
    # Advanced options
    with st.expander("Advanced Options"):
        address_purpose = st.selectbox("Address Type", 
                                      ["Any", "PRIMARY", "SECONDARY", "LOCATION", "MAILING"])
        limit = st.slider("Max Results", 1, 200, 10)
        
    if st.button("Search Providers", type="primary"):
        # Build search parameters
        params = {
            "version": API_VERSION,
            "limit": limit
        }
        
        # Add enumeration type if specified
        if search_type == "Organizations Only":
            params["enumeration_type"] = "NPI-2"
        elif search_type == "Individuals Only":
            params["enumeration_type"] = "NPI-1"
        
        # Add search criteria
        if org_name:
            params["organization_name"] = org_name
        if first_name:
            params["first_name"] = first_name
        if last_name:
            params["last_name"] = last_name
        if city:
            params["city"] = city
        if state:
            params["state"] = state.upper()
        if postal_code:
            params["postal_code"] = postal_code
        if taxonomy_desc:
            params["taxonomy_description"] = taxonomy_desc
        if address_purpose != "Any":
            params["address_purpose"] = address_purpose
        
        # Check if we have at least one search criterion
        search_criteria = [org_name, first_name, last_name, city, state, postal_code, taxonomy_desc]
        if any(search_criteria):
            with st.spinner("Searching..."):
                try:
                    response = requests.get(API_BASE_URL, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if debug_mode:
                        with st.expander("🔍 Search Parameters & Response"):
                            st.write("Search params:", params)
                            st.json(data)
                    
                    result_count = data.get("result_count", 0)
                    
                    if result_count > 0:
                        st.success(f"Found {result_count} provider(s)")
                        
                        # Process results
                        results = []
                        for result in data.get("results", []):
                            provider_info = extract_provider_info({"results": [result]})
                            if provider_info:
                                results.append(provider_info)
                        
                        if results:
                            results_df = pd.DataFrame(results)
                            
                            # Apply column filtering based on settings
                            if not show_all_columns:
                                if facility_focus:
                                    priority_cols = ['npi', 'entity_type', 'facility_name', 
                                                   'doing_business_as', 'primary_practice_city', 
                                                   'primary_practice_state', 'taxonomy_description']
                                else:
                                    priority_cols = ['npi', 'entity_type', 'name', 
                                                   'primary_practice_city', 'primary_practice_state', 
                                                   'taxonomy_description']
                                available_cols = [col for col in priority_cols if col in results_df.columns]
                                results_df = results_df[available_cols]
                            
                            st.dataframe(results_df, use_container_width=True)
                            
                            # Download button
                            csv = results_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Results as CSV",
                                data=csv,
                                file_name="npi_search_results.csv",
                                mime="text/csv"
                            )
                            
                            if result_count > limit:
                                st.info(f"Showing first {limit} results of {result_count} total. "
                                       f"Increase 'Max Results' in Advanced Options to see more.")
                    else:
                        st.warning("No providers found matching your search criteria.")
                        
                except requests.exceptions.RequestException as e:
                    st.error(f"Search failed: {str(e)}")
                except Exception as e:
                    st.error(f"Error processing results: {str(e)}")
        else:
            st.warning("Please enter at least one search criterion.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 12px;'>
    Data source: NPPES NPI Registry API v2.1 | 
    Note: Issuance of an NPI does not ensure or validate that the Health Care Provider is Licensed or Credentialed<br>
    💡 Tip: Enable Debug Mode in Display Settings to troubleshoot data extraction issues
</div>
""", unsafe_allow_html=True)
