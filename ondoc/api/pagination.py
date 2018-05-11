def paginate_queryset(queryset, request, page_size=20):

    page = int(request.query_params.get('page',1))

    if page_size<0 or page_size>100:
        page_size = 20

    if page<1:
        page=1

    offset = (page-1)*page_size
    return queryset[offset:page_size]